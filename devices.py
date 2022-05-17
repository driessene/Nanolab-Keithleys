from time import sleep
from pyvisa import ResourceManager


class Keithley2400:

    def __init__(self, address, max_current, measurements, soak, nplc=0.01, azero=False):
        self.meter = ResourceManager().open_resource(address)
        self.meter.write('*rst; status:preset; *cls')
        # configure service requests
        self.meter.write('status:measurement:enable 512')
        self.meter.write("*sre 1")
        # constant states
        self.meter.write('trigger:source immediate')
        self.meter.write('source:clear:auto off')
        self.meter.write('source:function voltage')
        self.meter.write('trace:feed sense1')
        # default properties
        self.max_current = max_current
        self.measurements = measurements
        self.output_enabled = False
        self.nplc = nplc
        self.soak = soak
        self.azero = azero

    @property
    def max_current(self):
        return float(self.meter.query('sense:current:protection:level?'))

    @max_current.setter
    def max_current(self, x):
        self.meter.write(f'sense:current:protection {x}')

    @property
    def measurements(self):
        return int(self.meter.query('trace:points?'))

    @measurements.setter
    def measurements(self, x):
        self.meter.write(f'trace:points {x}')
        self.meter.write(f'trigger:count {x}')

    @property
    def soak(self):
        return float(self.meter.query('source:delay?'))

    @soak.setter
    def soak(self, x):
        self.meter.write(f'source:delay {x}')

    @property
    def nplc(self):
        return float(self.meter.query('sense:current:nplcycles?'))

    @nplc.setter
    def nplc(self, x):
        self.meter.write(f'sense:current:nplcycles {x}')

    @property
    def azero(self):
        return bool(int(self.meter.query('system:azero?')))

    @azero.setter
    def azero(self, x):
        self.meter.write(f'system:azero:state {int(x)}')
        self.meter.write(f'system:azero:caching {int(x)}')

    @property
    def output_enabled(self):
        return bool(int(self.meter.query('output?')))

    @output_enabled.setter
    def output_enabled(self, x):
        self.meter.write(f'output {int(x)}')

    @property
    def target_voltage(self):
        return float(self.meter.query('source:voltage:level?'))

    @target_voltage.setter
    def target_voltage(self, x):
        self.meter.write(f'source:voltage:level {x}')

    def beep(self, freq, time):
        self.meter.write(f'system:beeper {freq}, {time}')

    def measure(self):
        # enable buffer
        self.meter.write('trace:feed:control next')
        # start procedure
        self.meter.write('initiate')
        # wait for buffer to fill
        self.meter.wait_for_srq(timeout=None)
        # calculate mean and sd. then store
        self.meter.write('calc3:form mean')
        voltage_mean, current_mean, *_ = eval(self.meter.query('calc3:data?'))
        self.meter.write('calc3:form sdev')
        voltage_sd, current_sd, *_ = eval(self.meter.query('calc3:data?'))
        # stop and clear buffer
        self.meter.write('abort')
        self.meter.write('*cls')
        return {'voltage': voltage_mean, 'voltage sd': voltage_sd, 'current': current_mean, 'current sd': current_sd}


class Keithley6485:
    def __init__(self, address, measurements, soak, nplc, azero=False):
        self.meter = ResourceManager().open_resource(address)
        self.meter.write('*rst; *cls')
        # configure service requests
        self.meter.write('status:measurement:enable 512')
        self.meter.write("*sre 1")
        # constant states
        self.meter.write('trigger:source immediate')
        self.meter.write('trace:feed sense')
        # default properties
        self.measurements = measurements
        self.nplc = nplc
        self.soak = soak
        self.azero = azero

    @property
    def measurements(self):
        return int(self.meter.query('trace:points?'))

    @measurements.setter
    def measurements(self, x):
        self.meter.write(f'trace:points {x}')
        self.meter.write(f'trigger:count {x}')

    @property
    def nplc(self):
        return float(self.meter.query('nplcycles?'))

    @nplc.setter
    def nplc(self, x):
        self.meter.write(f'nplcycles {x}')

    @property
    def azero(self):
        return bool(int(self.meter.query('system:azero?')))

    @azero.setter
    def azero(self, x):
        self.meter.write(f'system:azero:state {int(x)}')

    def measure(self):
        sleep(self.soak)
        # enable buffer
        self.meter.write('trace:feed:control next')
        # start procedure
        self.meter.write('initiate')
        # wait for buffer to fill
        self.meter.wait_for_srq(timeout=None)
        # calculate mean and sd. then store
        self.meter.write('calc3:form mean')
        current_mean = eval(self.meter.query('calc3:data?'))
        self.meter.write('calc3:form sdev')
        current_sd = eval(self.meter.query('calc3:data?'))
        # stop and clear buffer
        self.meter.write('abort')
        self.meter.write('*cls')
        return {'current': current_mean, 'current sd': current_sd}
