import procedures
import devices

dev = devices.Keithley6485('AMMETER', 100, 1, 0.1)
print(dev.measure())

#test = procedures.PicoSweep(
#    'PRIMARY',
#    'AMMETER',
#    -0.5,
#    0.5,
#    51,
#    50,
#    1,
#    1
#)
#
#test.execute().to_csv('C:/Users/2020e/Desktop/output.csv')