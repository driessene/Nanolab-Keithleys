# Nanolab-Keithley
Code for the Keithleys in the Nanolab

# devices.py
Contains all source meter objects. Contains all properties for Keithley2400 and Keithly6485
### initialize
Configures source meter
- address: communication address of source meter. Cannot be changed after initialization
- max_current: maximum current from source meter
- measurements: number of samples to fill the buffer with.
- soak: After applying voltage wait x seconds to measure
- npl: number of power line cycles
    - 0.01: fastest measurements, least accurate
    - 0.1: slowest measurements, most accurate
- azero:
    - True: for every current measurement, take a reference and zero measurement
    - False: don't use azero function
    - don't take more than 10 measurements with azero on
- output_enabled:
    - True: source is on
    - False: source is off
- target_voltage: output voltage of source meter. Note that this is not 100% accurate. This is why it is "target" and we manually measure voltage
### beep
- frequency: pitch of beep
- time: duration of beep
### measure
Fills buffer with voltage and current measurements. Returns mean and sd of both in a dictionary

# procedures.py
Contains all code for collecting data
## SweepPoints
array containing all target voltages for source meter. Inherited from numpy ndarray. Call regen() to change start, end, measurements, or scale.
- start: lowest voltage value
- end: highest voltage value
- points: number of voltages to apply to sample
- scale: set to either linear / lin or logarithmic / log. Sets spacing scale
- regen: enter any values you would like to change (start, end, points, or scale). Regenerates the whole array to fit new parameters
## Sweep
When recording data from a two-terminal device (such as a resistor)
- voltage_start: starting voltage in the sweep
- voltage_end: ending voltage in the sweep
- voltage_measurements: voltages between start and end to be recorded.
- max_current: maximum current from the voltage source, aka compliance current
- samples: current samples per voltage sample
- npl: number of power line cycles
    - 0.01: fastest measurements, least accurate
    - 0.1: slowest measurements, most accurate
- soak: delay (in seconds) after voltage turn-on and measurement collection
    - happens for every current measurement if azero is 1 as we need to wait for the voltage to stabilize after setting it to zero for the zero measurements in azero
    - happens for every voltage change if azero is 0
- azero:
    - True: for every current measurement, take a reference and zero measurement
    - False: don't use azero function. When false, wait for delay after every voltage change to maintain soak time
    - don't take more than 10 measurements with azero on
- scale:
    - linear / lin: voltage change is constant. ie linear sweep
    - logarithmic / log: voltage change grows. ie logarithmic sweep

Call measure to measure current values. Set i to index in dataframe
Call execute to fill entire dataframe
## DualSweep
When recording data from a three-terminal device (such as a transistor) in an embedded loop. Secondary changes first, then primary changes. Primary should be drain-source if measuring a transistor
secondary should be gate-source
- primary_start: starting voltage in the sweep
- primary_end: ending voltage in the sweep
- primary_measurements: voltages between start and end to be recorded.
- secondary_start: starting voltage in the sweep
- secondary_end: ending voltage in the sweep
- secondary_measurements: voltages between start and end to be recorded.
- primary_max_current: maximum current from the voltage source, aka compliance current
- secondary_max_current: maximum current from the voltage source, aka compliance current
- samples: current samples per voltage sample
- npl: number of power line cycles
    - 0.01 - fastest measurements, least accurate
    - 0.1 - slowest measurements, most accurate
- soak: delay (in seconds) after voltage turn-on and measurement collection
    - happens for every current measurement if azero is 1 as we need to wait for the voltage to stabilize after setting it to zero for the zero measurements in azero
    - happens for every voltage change if azero is 0
- azero:
    - True: for every current measurement, take a reference and zero measurement
    - False: don't use azero function. When false, wait for delay after every voltage change to maintain soak time
    - don't take more than 10 measurements with azero on
- primary_scale: spacing algorithm for the primary voltage sweep
    - linear: voltage change is constant. ie linear sweep
    - logarithmic: voltage change grows. ie logarithmic sweep
- secondary_scale: spacing algorithm for the secondary voltage sweep
    - linear: voltage change is constant. ie linear sweep
    - logarithmic: voltage change grows. ie logarithmic sweep

Call measure to measure current values. Set i to index in dataframe
Call execute to fill entire dataframe
## Picoammeter variation
PicoSweep or PicoDualSweep. Same as Sweep and DualSweep respectfully, but with added parameter ammeter_address. When using ammeter, put it in series with Primary_Sourcemeter. Current data from Primary_Sourcemeter switched for ammeter.

# data_analysis.py
contains all code for processing recorded data.
## to_excel(path, **kwargs)
- path: Destination of save file
- kwargs: all other keyword arguments should be data frames. Key is sheet name, value is to be saved
## Analysis
a subclass of pandas.dataframe, so all of those functions should apply when analyzing any data from sweep or dual sweep
When initializing, accepts any dataframe or path to an Excel or pickle file previously output by this program, sweep, or dual-sweep. Should have voltage, voltage SD, current, current SD columns at a minimum to work with. if from dual_sweep, should have those columns plus the same but with a 'secondary' prefix.
### read
output dataframe to a file for future reference
    - path: pass in a Path from pathlib
### write
- path: pass in a Path from pathlib
    - csv: generally bad unless you will never use this program again and don't have Excel
    - xlsx: generally bad unless you will never use this program again
    - pkl: generally good, but bigger than feather. Only readable by python
    - parquet: Excellent for archiving
    - feather: Excellent for caching
### zero
set voltage at zero to have a current of zero. Changes all current data by the offset
    - inplace: if true, replaces dataframe as the output of the function. Default is false
### invert current
change the polarity of the current. ie: flips current across x-axis
    - primary: if true, flip primary current. Default is true
    - secondary: if true and secondary exists, flip secondary. Default is false
    - inplace: if true, replaces dataframe as the output of the function. Default is false
### switching current
Returns a data frame. Values equal max current / min current for each primary voltage. Two columns: first is where secondary voltage is positive, second is where secondary voltage is negative
### fowler_nordheim_transform
Returns a dataframe with fn_x, fn_x SD, fn_y, fn_y SD, and secondary voltage if it exists
- voltage_name: What column to treat as voltage in calculations. Default is voltage
- current_name: What column to treat as current in calculations. Default is current
### plot
Plots two graphs (voltage vs current, Fowler Nordheim) if from Sweep, four (voltage vs current, secondary voltage vs current, fn, current heatmap) if from DualSweep. 
- path: Saves to path. If path is not set, don't save.
- current_name: Which current source to plot. Default is current
- line_cmap: If from dual sweep, cmap for line plots. Default is inferno
- heat_cmap: If from dual sweep, cmap for the heatmap. Default is inferno
- use a diverging map if the minimum applied voltage is of the same magnitude as the max
- [color options](https://matplotlib.org/stable/tutorials/colors/colormaps.html)
- shading: Shading algorithm for the heatmap. Default is auto
    - gouraud is nice to see a smoothing effect if you have a lot of data. Don't use it on small datasets as you lose some data
    - [all options (see "shading")](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.pcolormesh.html#matplotlib.axes.Axes.pcolormesh)
- width: width of figure in inches. Default = 11
- height: height of figure in inches. Default = 8.5
- dpi: dots per inch of figure. Default = 100