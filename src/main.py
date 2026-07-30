import config
import asyncio
# import network
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
import websocket
from device import Device
import led_effects
# import machine

# wifi = network.WLAN(network.STA_IF)

update_sensors_query = """
mutation ($id: Int!, $airQuality: Float, $humidity: Float = 1.5, $occupied: Boolean, $temperature: Float) {
    updateSensors(
        id: $id
        sensors: {airQuality: $airQuality, humidity: $humidity, temperature: $temperature, occupied: $occupied}
    ) {
        success
    }
}
"""

# async def connnect_to_wifi():
#     if not wifi.active():
#         wifi.active(True)
#         wifi.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
#     while not wifi.isconnected():
#         print(wifi.status())
#         await asyncio.sleep(1)

async def main():
    leds = led_effects.LedChain(config.led_pins)
    segments, led_splitter = led_effects.make_segments(config.led_segments)
    asyncio.create_task(led_effects.led_engine(leds, led_splitter))
    # await connnect_to_wifi()

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        adc = ADS.ADS1115(i2c, address=config.ADS1115_ADDRESS)
        adc.gain = config.ADS1115_GAIN
        print("ADS1115 ready")
    except Exception as e:
        print(f"ADS1115 unavailable, gas sensing disabled: {e}")
        adc = None

    ws = websocket.WebSocket()
    await ws.connect(config.GRAPHQL_HOST, config.GRAPHQL_PORT, config.GRAPHQL_PATH)
    gql = websocket.GraphQLWs(ws)
    await gql.connect()
    asyncio.create_task(gql.handler())
    print("connected")
    for c in config.devices:
        device = Device(c, gql, segments, adc=adc)
        # asyncio.create_task(device.presence_handler())
        asyncio.create_task(device.led_update_handler())
        # asyncio.create_task(device.read_dht_loop())
        asyncio.create_task(device.read_misc_loop())
        asyncio.create_task(device.update_sensors_loop())

loop = asyncio.new_event_loop()
loop.create_task(main())
loop.run_forever() # TODO make use a task group instead of a run_forever?
