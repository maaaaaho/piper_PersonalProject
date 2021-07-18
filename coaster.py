#!/usr/bin/env python
import os
import time
import json
import sys
import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import RPi.GPIO as GPIO

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

#Init AWSIoTMQTTClient
myMQTTClient = AWSIoTMQTTClient("raspberry-pi")
myMQTTClient.configureEndpoint("a25lv8edwvpzsv-ats.iot.ap-northeast-1.amazonaws.com", 8883)
myMQTTClient.configureCredentials("/home/pi/cert/AmazonRootCA1.pem", "/home/pi/cert/50b0377edf-private.pem.key", "/home/pi/cert/50b0377edf-certificate.pem.crt")

#AWSIoTMQTTClient connection config
myMQTTClient.configureOfflinePublishQueueing(-1)
myMQTTClient.configureDrainingFrequency(2)
myMQTTClient.configureConnectDisconnectTimeout(10)
myMQTTClient.configureMQTTOperationTimeout(5)


#loadcell config
EMULATE_HX711=False

#referenceUnit = 1
referenceUnit = 456

if not EMULATE_HX711:
    import RPi.GPIO as GPIO
    from hx711 import HX711
else:
    from emulated_hx711 import HX711

def cleanAndExit():
    print("Cleaning...")

    if not EMULATE_HX711:
        GPIO.cleanup()
        
    print("Bye!")
    sys.exit()

hx = HX711(5, 6)

# I've found out that, for some reason, the order of the bytes is not always the same between versions of python, numpy and the hx711 itself.
# Still need to figure out why does it change.
# If you're experiencing super random values, change these values to MSB or LSB until to get more stable values.
# There is some code below to debug and log the order of the bits and the bytes.
# The first parameter is the order in which the bytes are used to build the "long" value.
# The second paramter is the order of the bits inside each byte.
# According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
hx.set_reading_format("MSB", "MSB")

# HOW TO CALCULATE THE REFFERENCE UNIT
# To set the reference unit to 1. Put 1kg on your sensor or anything you have and know exactly how much it weights.
# In this case, 92 is 1 gram because, with 1 as a reference unit I got numbers near 0 without any weight
# and I got numbers around 184000 when I added 2kg. So, according to the rule of thirds:
# If 2000 grams is 184000 then 1000 grams is 184000 / 2000 = 92.
hx.set_reference_unit(referenceUnit)
#hx.set_reference_unit(referenceUnit)
hx.reset()
hx.tare()

#connect and subscribe to AWS IoT
myMQTTClient.connect()

#Initial
time.sleep(2)

topic = "sensor/weight"

while True:
    try:
        # These three lines are usefull to debug wether to use MSB or LSB in the reading formats
        # for the first parameter of "hx.set_reading_format("LSB", "MSB")".
        # Comment the two lines "val = hx.get_weight(5)" and "print val" and uncomment these three lines to see what it prints.
        
        # np_arr8_string = hx.get_np_arr8_string()
        # binary_string = hx.get_binary_string()
        # print binary_string + " " + np_arr8_string
        
        # Prints the weight. Comment if you're debbuging the MSB and LSB issue.
        val = round(hx.get_weight(5))
        nowtime = datetime.datetime.now()
        print(str(datetime.datetime.now()) +","+ str(val))
        data = {
            'device': "pi",
            'date':str(datetime.date.today()),
            'time':str(nowtime.hour)+":"+str(nowtime.minute)+":"+str(nowtime.second),
            'weight': val
        }
        print(data)
        #print(val)
        myMQTTClient.publish(topic, json.dumps(data), 1)

        # To get weight from both channels (if you have load cells hooked up 
        # to both channel A and B), do something like this
        #val_A = hx.get_weight_A(5)
        #val_B = hx.get_weight_B(5)
        #print "A: %s  B: %s" % ( val_A, val_B )

        hx.power_down()
        hx.power_up()
        time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()


#----------------------------------------------------------------
#	Note:
#		ds18b20's data pin must be connected to pin7(GPIO4).
#----------------------------------------------------------------

# Reads temperature from sensor and prints to stdout
# id is the id of the sensor
def readSensor(id):
	tfile = open("/sys/bus/w1/devices/"+id+"/w1_slave")
	text = tfile.read()
	tfile.close()
	secondline = text.split("\n")[1]
	temperaturedata = secondline.split(" ")[9]
	temperature = float(temperaturedata[2:])
	temperature = temperature / 1000
	myMQTTClient.connect()
	myMQTTClient.publish("myTopic", temperature, 0)
	#print "Sensor: " + id  + " - Current temperature : %0.3f C" % temperature


# Reads temperature from all sensors found in /sys/bus/w1/devices/
# starting with "28-...
def readSensors():
	count = 0
	sensor = ""
	for file in os.listdir("/sys/bus/w1/devices/"):
		if (file.startswith("28-")):
			readSensor(file)
			count+=1
	if (count == 0):
		myMQTTClient.connect()
		myMQTTClient.publish("myTopic", "sensor found! Check connection", 0)
		#print "No sensor found! Check connection"
