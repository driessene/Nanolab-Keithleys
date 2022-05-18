from pathlib import Path
from math import log
from numpy import around, zeros
from pandas import DataFrame, ExcelWriter, read_parquet, read_pickle, read_excel, read_feather, read_csv
from matplotlib import pyplot as plt
from seaborn import lineplot, heatmap


# puts all kwargs into an Excel file.
def to_excel(path, **kwargs):
    with ExcelWriter(path=path) as writer:
        for sheet, frame in kwargs.items():
            frame.to_excel(writer, sheet_name=sheet)


# used for analyzing any output from sweep or dual sweep
class Analysis(DataFrame):
    def __init__(self, df):
        if isinstance(df, DataFrame):
            super().__init__(df)
        elif isinstance(df, Path):
            super().__init__(self.read(df))
        else:
            raise TypeError('init parameter must either be a dataframe or a path to a saved dataframe')

    # read from previous write()
    @staticmethod
    def read(path: Path):
        match path.suffix:
            case '.csv':
                out = read_csv(path, index_col=None)
            case '.xlsx':
                out = read_excel(path).reset_index(())
                if 'secondary voltage' in out:
                    out = read_excel(path, index_col=[0, 1]).reset_index()
            case '.pkl':
                out = read_pickle(path).reset_index()
            case '.parquet':
                out = read_parquet(path).reset_index()
            case '.fea' | '.feather':
                out = read_feather(path).reset_index()
            case _:
                raise ValueError(f'{path.suffix} is not supported. Try .csv, .xlsx, .pkl, .parquet, or .fea / .feather')
        return out

    # save self to reference later
    def write(self, path: Path):

        match path.suffix:
            case '.csv':
                self.voltage_index().to_csv(path)
            case '.xlsx':
                self.voltage_index().to_excel(path)
            case '.pkl':
                self.voltage_index().to_pickle(path)
            case '.parquet':
                self.voltage_index().to_parquet(path)
            case '.fea' | '.feather':
                self.voltage_index().reset_index().to_feather(path)
            case _:
                raise ValueError(f'{path.suffix} is not supported. Try .csv, .xlsx, .pkl, .parquet, or .fea / .feather')

    def voltage_index(self):
        if 'secondary voltage' in self:
            return self.set_index(['voltage', 'secondary voltage'])
        else:
            return self.set_index('voltage')

    def zero(self, inplace=False):
        def find_zero(df):
            volt = df['voltage']
            pv = volt[volt <= 0]
            nv = volt[volt <= 0]
            min_pv = min(pv, key=abs)
            min_nv = min(nv, key=abs)

            df.set_index('voltage', inplace=True)
            min_nc = df.at[min_nv, 'current']
            min_pc = df.at[min_pv, 'current']

            if abs(min_pv) > abs(min_nv):
                return min_pc
            elif abs(min_pv) < abs(min_nv):
                return min_nc
            elif abs(min_pv) == abs(min_nv):
                return (min_nc + min_pc) / 2

        if 'secondary voltage' in self:
            voltages = self['secondary voltage'].unique()
            vals = zeros(len(voltages))
            for i, sv in enumerate(voltages):
                op = self[self['secondary voltage'].eq(sv)]
                vals[i] = find_zero(op.copy())
            cal = vals.mean()
        else:
            cal = find_zero(self.copy())

        op = self.copy()
        op['current'] = op['current'].apply(lambda x: x - cal)
        if inplace:
            self.loc[:, :] = op
        return op

    def invert_current(self, primary=True, secondary=False, inplace=False):
        output = self.copy()
        if primary:
            output.loc[:, 'current'] = output.loc[:, 'current'].mul(-1)
        if 'secondary current' in output and secondary:
            output.loc[:, 'secondary current'] = output.loc[:, 'secondary current'].mul(-1)
        if inplace:
            self.loc[:, :] = output
        return output

    # returns switching current_name value (i_max / i_min) of a transistor for each drain voltage. Returns none if not from dual_sweep
    def switching_current(self):
        if 'secondary voltage' in self:
            out = DataFrame(index=self['voltage'].unique(), columns=['positive', 'negative'])
            for voltage in out.index:
                op = self[self['voltage'].eq(voltage)]
                opp = op[op['secondary voltage'] >= 0]['current']
                opn = op[op['secondary voltage'] <= 0]['current']
                out.at[voltage, 'positive'] = opp.max() / opp.min()
                out.at[voltage, 'negative'] = opn.min() / opn.max()
            return out
        else:
            return

    # return dataframe to be plotted to show fn curves
    def fowler_nordheim_transform(self, voltage_name='voltage', current_name='current'):
        # transform on the x-axis
        def x_transform(voltage):
            try:
                return 1 / voltage
            except ZeroDivisionError:
                return None

        def x_sd(voltage, voltage_sd):
            try:
                return 1 / voltage * voltage_sd ** 0.5
            except ZeroDivisionError:
                return None

        # transform on the y-axis
        def y_transform(voltage, current):
            try:
                return log(abs(current / (voltage ** 2)))
            except(ValueError, ZeroDivisionError):
                return None

        def y_sd(current, current_sd, voltage, voltage_sd):
            try:
                return ((2 / voltage * voltage_sd) ** 2 + (1 / current * current_sd) ** 2) ** 0.5
            except ZeroDivisionError:
                return None

        # apply transforms
        out = DataFrame({
            'fn_x': self.apply(lambda x: x_transform(x[voltage_name]), axis=1),
            'fn_x sd': self.apply(lambda x: x_sd(x[voltage_name], x[f'{voltage_name} sd']), axis=1),
            'fn_y': self.apply(lambda x: y_transform(x[voltage_name], x[current_name]), axis=1),
            'fn_y sd': self.apply(lambda x: y_sd(x[current_name], x[f'{current_name} sd'], x[voltage_name], x[f'{voltage_name} sd']), axis=1)
        })
        if 'secondary voltage' in self:
            out['secondary voltage'] = self['secondary voltage']
        return out

    # displays all ways of analyzing data. 2 for single sweep, 4 for dual sweep
    def plot(self, path=None, current_name='current', line_cmap='inferno', heat_cmap='inferno', shading='auto', width=11,
             height=8.5, dpi=100):
        if 'secondary voltage' in self:
            fig, axs = plt.subplots(2, 2, constrained_layout=True)
            heat = self.pivot_table(current_name, 'voltage', 'secondary voltage')
            heat.index, heat.columns, = around(heat.index, 2), around(heat.columns, 2)
            # primary vs current_name
            g = lineplot(ax=axs[0, 0], x='voltage', y=current_name, hue='secondary voltage', data=self, ci=None, legend=False, palette=line_cmap)
            g.set_title('Primary VS Current')
            cb = g.figure.colorbar(plt.cm.ScalarMappable(cmap=line_cmap, norm=plt.Normalize(self['secondary voltage'].min(), self['secondary voltage'].max())), ax=axs[:, 0], aspect=40, label='secondary voltage')
            cb.outline.set_linewidth(0)
            # secondary vs current_name
            g = lineplot(ax=axs[0, 1], x='secondary voltage', y=current_name, hue='voltage', data=self, ci=None, legend=False, palette=line_cmap)
            g.set_title('Secondary VS Current')
            cb = g.figure.colorbar(plt.cm.ScalarMappable(cmap=line_cmap, norm=plt.Normalize(self['voltage'].min(), self['voltage'].max())), ax=axs[0, 1], label='voltage')
            cb.outline.set_linewidth(0)
            # fowler nordheim
            g = lineplot(ax=axs[1, 0], x='fn_x', y='fn_y', hue='secondary voltage', data=self.fowler_nordheim_transform(current_name=current_name), ci=None, legend=False, palette=line_cmap)
            g.set_title('Fowler Nordheim')
            # voltage heatmap
            g = heatmap(ax=axs[1, 1], data=heat, cmap=heat_cmap, cbar_kws={'label': current_name}, shading=shading)
            g.set_title('Voltage Heatmap')
            g.invert_yaxis()
        else:
            fig, axs = plt.subplots(1, 2, constrained_layout=True)
            # voltage vs current_name
            lineplot(ax=axs[0], x='voltage', y=current_name, data=self)
            # fowler nordheim
            lineplot(ax=axs[1], x='fn_x', y='fn_y', data=self.fowler_nordheim_transform())
        fig.set_size_inches(width, height)
        fig.set_dpi(dpi)
        if path is not None:
            plt.savefig(path, dpi=dpi)
        plt.show()
