#!/usr/bin/env python3
# *-* coding: utf-8 *-*

from pycalima.pycalima.Calima import Calima
from datetime import datetime
import sys, getopt, time, json
import paho.mqtt.client as mqtt

MQTT_BROKER=""
MQTT_PORT=1883
MQTT_USER=""
MQTT_PASSWD=""
MQTT_CLIENT="CalimaMQTT"

MQTT_TOPIC_PREFIX="homeassistant" # No trailing slash

CALIMA_MAC="xx:xx:xx:xx:xx:xx"
CALIMA_PIN="xxxxxxxx"

CALIMA_DEVICE=CALIMA_MAC.replace(":","")

storedSpeed=1000 # Default speed setting

def dateTime() :
  return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# After connection to broker, subscribe to the relevant topics
def on_connect(client, userdata, flags, rc):
    print(f"[{dateTime()}] DEBUG: Connected to MQTT broker with result code {rc}")
    client.subscribe([(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/set",0)])
    client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/available","online")

# Callback for mqtt set
def on_message_Set(client, userdata, msg):
  global storedSpeed
  x=msg.payload.decode("utf-8")
  print(f"[{dateTime()}] DEBUG: Received: "+x)

  if "speed" in json.loads(x) :
    speed=roundToMultiple(int(json.loads(x)["speed"]))
    print(f"[{dateTime()}] DEBUG: Rounded speed to {speed}")
    fan.setFanSpeedSettings(2250,1625,speed)
    client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/speed/state",str(int(json.loads(x)["speed"]))) #,qos=0,retain=True) # Publish speed to mqtt keeper

  if "mode" in json.loads(x) :
    if "Boost" in json.loads(x)["mode"] :
      fan.setBoostMode(1,2500,20)

  if "state" in json.loads(x) :
    if "OFF" in json.loads(x)["state"] :
      client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/state","OFF") # WORKAROUND: Publish state for HA switch to work
      storedSpeed=fan.getFanSpeedSettings()[2]
      print(f"[{dateTime()}] DEBUG: Saved speed {storedSpeed} before turning off")
      fan.setFanSpeedSettings(2250,1625,0)
      client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/speed/state",0) # Publish speed to mqtt keeper
    if "ON" in json.loads(x)["state"] :
      client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/state","ON") # WORKAROUND: Publish state for HA swith to work
      print(f"[{dateTime()}] DEBUG: Using saved speed {storedSpeed}")
      fan.setFanSpeedSettings(2250,1625,storedSpeed)
      client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/speed/state",str(storedSpeed)) # Publish speed to mqtt keeper

def roundToMultiple(number,multiple=25) :
  return multiple * round(number / multiple)

def conCalima() :
  print(f"[{dateTime()}] DEBUG: Trying to Connect to Calima...")
  return Calima(CALIMA_MAC, CALIMA_PIN) # Connect to Calima


def conMqtt() :
  client = mqtt.Client(MQTT_CLIENT) # Create MQTT client
  client.on_connect = on_connect # Register on_connect method
  client.message_callback_add(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/set", on_message_Set) # Register callback for SetRpm
  client.username_pw_set(MQTT_USER, MQTT_PASSWD) # Set broker user/password
  client.connect(MQTT_BROKER, MQTT_PORT) # Connect to broker
  client.loop_start() # Run network loop

  #fan.setAlias("Tvättstugan")
  #time.sleep(10)
  return client

def initMqttDevice(client):
  # Json string for device, will be reused for each sensor
  JSON_DEVICE = (
  "\"device\":{"
    f"\"identifiers\":\"{CALIMA_DEVICE}\","
    f"\"name\":\"{CALIMA_NAME}\","
    "\"sw_version\":\"0.5\","
    "\"manufacturer\":\"PAX\","
    "\"model\":\"Calima\"}"
  )

  # Create mqtt device
  client.publish(MQTT_TOPIC_PREFIX+"/fan/calima_"+CALIMA_DEVICE+"/fan/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_fan\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_fan\",
     \"name\": \""""+CALIMA_NAME+"""\",
     \"command_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/set\",
     \"command_template\": \"{\\"state\\": \\"{{ value }}\\"}\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/state\",
     \"availability_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/available\",
     \"preset_modes\": [\"Boost\",\"Trickle ventilation\"],
     \"preset_mode_state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"preset_mode_value_template\": \"{{ value_json.mode }}\",
     \"preset_mode_command_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/set\",
     \"preset_mode_command_template\": \"{\\"mode\\": \\"{{ value }}\\"}\",
     \"percentage_command_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/set\",
     \"percentage_command_template\": \"{\\"speed\\": \\"{{ value }}\\"}\",
     \"percentage_state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/fan/calima_"""+CALIMA_DEVICE+"""/speed/state\",
     \"speed_range_max\": 1625,
     \"speed_range_min\": 1,
     \"optimistic\": \"false\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)
  # String to implement all modes, see above
  #   \"preset_modes\": [\"Boost\",\"Trickle ventilation\",\"Light ventilation\",\"Humidity ventilation\"],
  # Trickle max is 1625. Can be set higher (2500?) for other modes
  #   \"speed_range_max\": 1625,


  # Create sensors
  client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/rpm/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_rpm\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_rpm\",
     \"name\": \"Speed\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"unit_of_measurement\": \"RPM\",
     \"value_template\": \"{{ value_json.rpm }}\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)
  client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/temp/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_temp\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_temp\",
     \"name\": \"Temperature\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"unit_of_measurement\": \"°C\",
     \"device_class\":\"temperature\",
     \"value_template\": \"{{ value_json.temp }}\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)
  client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/hum/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_hum\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_hum\",
     \"name\": \"Humidity\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"unit_of_measurement\": \"%\",
     \"device_class\":\"humidity\",
     \"value_template\": \"{{ value_json.hum }}\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)
  client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/light/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_light\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_light\",
     \"name\": \"Light\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"unit_of_measurement\": \"Lux\",
     \"value_template\": \"{{ value_json.light }}\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)
  client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/mode/config","""
    {
     \"unique_id\": \""""+CALIMA_DEVICE+"""_mode\",
     \"object_id\": \""""+CALIMA_DEVICE+"""_mode\",
     \"name\": \"Mode\",
     \"state_topic\": \""""+MQTT_TOPIC_PREFIX+"""/sensor/calima_"""+CALIMA_DEVICE+"""/state\",
     \"value_template\": \"{{ value_json.mode }}\",
     """+JSON_DEVICE+"""
    }
    """,qos=0,retain=True)


def doMain(fan,client):
  print(f"[{dateTime()}] DEBUG: Running...")
  while True:
    try:
      v=fan.getState()
      json="{\"rpm\":"+str(v[3])+",\"temp\":"+str(v[1])+",\"hum\":"+str(v[0])+",\"light\":"+str(v[2])+",\"mode\":\""+str(v[4])+"\"}"
      client.publish(MQTT_TOPIC_PREFIX+"/sensor/calima_"+CALIMA_DEVICE+"/state",json)
      #print(json)
      time.sleep(10)


    except KeyboardInterrupt:
      print (f"[{dateTime()}] DEBUG: Ctrl-C caught, exiting...")
      fan.disconnect()
      client.disconnect()
      client.loop_stop()
      break
    except Exception as e:
      print(f"[{dateTime()}] DEBUG: Exception: {e}")
  #    fan.disconnect() # Tear down connection
      client.disconnect()
      client.loop_stop()
      time.sleep(3) # Wait for disconnect
      fan = conCalima() # Reconnect to Calima
      client=conMqtt() # Reconnect to MQTT
      time.sleep(3) # Let MQTT have time to connect
      doMain(fan,client) # Try running again
      break

# Initial setup
fan=conCalima()
CALIMA_NAME=fan.getAlias().rstrip('\x00') # And remove trailing zeros from the bytearray
# Check for name to validate connection and naming of the device
print(f"[{dateTime()}] DEBUG: Connected to Calima: {CALIMA_NAME}")
client=conMqtt() # Connect to MQTT
initMqttDevice(client) # Setup MQTT device
time.sleep(3) # Let MQTT have time to connect
doMain(fan,client) # Run main loop
