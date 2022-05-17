import devices
from concurrent.futures import ThreadPoolExecutor
from numpy import ndarray, linspace, geomspace
from pandas import DataFrame, RangeIndex
from tqdm.autonotebook import tqdm
from datetime import timedelta
from time import sleep


class SweepPoints(ndarray):
    def __new__(cls, start, end, points, scale):
        match scale:
            case 'linear' | 'lin':
                out = linspace(start, end, points).view(cls)
            case 'logarithmic' | 'log':
                out = geomspace(start, end, points).view(cls)
            case _:
                raise ValueError('scale must be either linear or logarithmic')
        out.scale = scale
        return out

    def regen(self, **kwargs):
        start = self[0]
        points = len(self)
        end = self[points - 1]
        scale = self.scale
        for key, item in kwargs.items():
            match key:
                case 'start':
                    start = item
                case 'end':
                    end = item
                case 'points':
                    points = item
                case 'scale':
                    scale = item
                case _:
                    raise ValueError(f'{key} is not an accepted kwarg. Try start, end, points, or scale.')
        new = SweepPoints(start, end, points, scale)
        self[:] = new[:]
        self.__dict__.update(new.__dict__)


class Sweep:
    def __init__(self, address, start, end, measurements, max_current, samples, nplc, soak, azero=False, scale='linear'):
        a = {True: soak, False: 0}
        self.soak = a[not azero]
        self.sourcemeter = devices.Keithley2400(address, max_current, samples, a[azero], nplc, azero)
        self.voltages = SweepPoints(start, end, measurements, scale)
        self.df = DataFrame(index=RangeIndex(stop=measurements), columns=['voltage', 'voltage sd', 'current', 'current sd'])

    def duration(self):
        return timedelta(seconds=len(self.voltages) * (self.sourcemeter.measurements * (self.sourcemeter.nplc / 60 + self.sourcemeter.soak) + self.soak))

    def measure(self, i):
        self.df.iloc[i] = self.sourcemeter.measure()

    def execute(self):
        self.sourcemeter.beep(1000, 1)
        self.sourcemeter.output_enabled = True
        for i, voltage in enumerate(tqdm(self.voltages)):
            # set output voltage
            self.sourcemeter.target_voltage = voltage
            # sleep for soak time
            sleep(self.soak)
            # collect and store data
            self.measure(i)

        # shutdown and return data
        self.sourcemeter.target_voltage = 0
        self.sourcemeter.output_enabled = False
        return self.df


class DualSweep:
    def __init__(self, primary_address, secondary_address, primary_start, primary_end, primary_measurements, secondary_start, secondary_end, secondary_measurements, primary_max_current, secondary_max_current, samples, nplc, soak, azero=False, primary_scale='linear', secondary_scale='linear'):
        a = {True: soak, False: 0}
        self.soak = a[not azero]
        self.primary_sourcemeter = devices.Keithley2400(primary_address, primary_max_current, samples, a[azero], nplc, azero)
        self.secondary_sourcemeter = devices.Keithley2400(secondary_address, secondary_max_current, samples, a[azero], nplc, azero)
        self.primary_voltages = SweepPoints(primary_start, primary_end, primary_measurements, primary_scale)
        self.secondary_voltages = SweepPoints(secondary_start, secondary_end, secondary_measurements, secondary_scale)
        self.primary_df = DataFrame(index=RangeIndex(stop=primary_measurements * secondary_measurements), columns=['voltage', 'voltage sd', 'current', 'current sd'])
        self.secondary_df = self.primary_df.copy()

    def duration(self):
        return timedelta(seconds=len(self.primary_voltages) * len(self.secondary_voltages) * (self.primary_sourcemeter.measurements * (self.primary_sourcemeter.nplc / 60 + self.primary_sourcemeter.soak) + self.soak))

    def measure(self, i, j):
        with ThreadPoolExecutor() as executor:
            f1 = executor.submit(self.primary_sourcemeter.measure)
            f2 = executor.submit(self.secondary_sourcemeter.measure)
            # store results
            self.primary_df.iloc[i * len(self.secondary_voltages) + j] = f1.result()
            self.secondary_df.iloc[i * len(self.secondary_voltages) + j] = f2.result()

    def execute(self):
        self.primary_sourcemeter.beep(1000, 1)
        self.secondary_sourcemeter.beep(2000, 2)
        self.primary_sourcemeter.output_enabled = True
        self.secondary_sourcemeter.output_enabled = True
        for i, pv in enumerate(tqdm(self.primary_voltages)):
            # set primary voltage
            self.primary_sourcemeter.target_voltage = pv
            for j, sv in enumerate(self.secondary_voltages):
                # set secondary voltage
                self.secondary_sourcemeter.target_voltage = sv
                # sleep for soak time
                sleep(self.soak)
                # run both measurements at the same time
                self.measure(i, j)

        # shutdown and return data
        self.primary_sourcemeter.target_voltage = 0
        self.primary_sourcemeter.output_enabled = False
        self.secondary_sourcemeter.target_voltage = 0
        self.secondary_sourcemeter.output_enabled = False
        return self.primary_df.join(self.secondary_df.add_prefix('secondary '))


class PicoSweep(Sweep):
    def __init__(self, voltmeter_address, ammeter_address, start, end, measurements, samples, nplc, soak, azero=False, scale='linear'):
        a = {True: soak, False: 0}
        super().__init__(voltmeter_address, start, end, measurements, 1e-6, samples, nplc, soak, azero, scale)
        self.ammeter = devices.Keithley6485(ammeter_address, samples, a[azero], nplc, azero)

    def measure(self, i):
        with ThreadPoolExecutor() as executor:
            f1 = executor.submit(self.sourcemeter.measure)
            f2 = executor.submit(self.ammeter.measure)
            f1r = f1.result()
            f1r['current'], f1r['current sd'] = f2.result().values()
            self.df.iloc[i] = f1r


class PicoDualSweep(DualSweep):
    def __init__(self, primary_address, secondary_address, ammeter_address, primary_start, primary_end, primary_measurements, secondary_start, secondary_end, secondary_measurements, secondary_max_current, samples, nplc, soak, azero=False, primary_scale='linear', secondary_scale='linear'):
        a = {True: soak, False: 0}
        super().__init__(primary_address, secondary_address, primary_start, primary_end, primary_measurements, secondary_start, secondary_end, secondary_measurements, 1e-6, secondary_max_current, samples, nplc, soak, azero, primary_scale, secondary_scale)
        self.ammeter = devices.Keithley6485(ammeter_address, samples, a[azero], nplc, azero)

    def measure(self, i, j):
        with ThreadPoolExecutor() as executor:
            f1 = executor.submit(self.primary_sourcemeter.measure)
            f2 = executor.submit(self.ammeter.measure)
            f3 = executor.submit(self.secondary_sourcemeter.measure)
            # store results
            f1r = f1.result()
            f1r['current'], f1r['current sd'] = f2.result().values()
            self.primary_df.iloc[i * len(self.secondary_voltages) + j] = f1r
            self.secondary_df.iloc[i * len(self.secondary_voltages) + j] = f3.result()
