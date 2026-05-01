import asyncio
import digitalio

led_update_sub = """
subscription ($id: Int = 0) {
  ledStateChanged(id: $id)
}
"""

led_update_query = """
query ($id: Int = 0) {
  model {
    getDevice(id: $id) {
      ledState
    }
  }
}
"""

update_sensors_query = """
mutation ($id: Int!, $airQuality: Float, $humidity: Float = 1.5, $occupied: Boolean, $temperature: Float, $smokeDetected: Boolean) {
    updateSensors(
        id: $id
        sensors: {airQuality: $airQuality, humidity: $humidity, temperature: $temperature, occupied: $occupied, smokeDetected: $smokeDetected}
    ) {
        success
    }
}
"""

class Device:
    def __init__(self, config, gql, segments):
        self.config = config
        self.gql = gql
        self.segments = []
        # self.temperature = None
        # self.humidity = None
        self.smokeDetected = None
        # self.occupied = None
        # self.airQuality = None

        for name in config["LED_SEGMENTS"]:
            self.segments.append(segments[name])

        # if "DHT_PIN" in config:
        #     self.dht = DHT22(machine.Pin(config["DHT_PIN"]))
        # else:
        #     self.dht = None

        if "AIR_DIN_PIN" in config:
            self.din = digitalio.DigitalInOut(config["AIR_DIN_PIN"])
            self.din.switch_to_input()
        else:
            self.din = None

        # if "AIR_ADC_PIN" in config:
        #     self.adc = machine.ADC(config["AIR_ADC_PIN"])
        # else:
        #     self.adc = None

        # if "PRESENCE_PIN" in config:
        #     self.presence_pin = machine.Pin(config["PRESENCE_PIN"], machine.Pin.IN)
        # else:
        #     self.presence_pin = None
        
        # if "PRESENCE_UART_CONTROLLER" in config:
        #     print(f'{config["PRESENCE_UART_CONTROLLER"]} {config["PRESENCE_TX_PIN"]} {config["PRESENCE_RX_PIN"]}')
        #     # self.presence_uart = machine.UART(config["PRESENCE_UART_CONTROLLER"], tx=config["PRESENCE_TX_PIN"], rx=config["PRESENCE_RX_PIN"])
        #     self.presence = hilink.HiLink(config["PRESENCE_UART_CONTROLLER"], tx=config["PRESENCE_TX_PIN"], rx=config["PRESENCE_RX_PIN"])
        # else:
        #     self.presence_uart = None
        #     self.presence = None

    # async def config_presence(self):
    #     if self.presence is None:
    #         return
    #     # print("configuring")
    #     # await self.presence.enable_config()
    #     # print("setting resolution")
    #     # await self.presence.set_resolution(hilink.HiLink.SHORT_RESOLUTION)
    #     # print("setting running config")
    #     # # await self.presence.run_automatic_config()
    #     # # each gate is about 7.87 inches
    #     # print("setting max")
    #     # await self.presence.set_max_gate_and_duration(1, 0, 1)
    #     # await self.presence.set_gate_sensitivity(0, 99, 100)
    #     # await self.presence.set_gate_sensitivity(1, 99, 100)
    #     # await self.presence.set_gate_sensitivity(2, 100, 100)
    #     # await self.presence.set_gate_sensitivity(3, 100, 100)
    #     # await self.presence.set_gate_sensitivity(4, 100, 100)
    #     # await self.presence.set_gate_sensitivity(5, 100, 100)
    #     # await self.presence.set_gate_sensitivity(6, 100, 100)
    #     # await self.presence.set_gate_sensitivity(7, 100, 100)
    #     # await self.presence.set_gate_sensitivity(8, 100, 100)
    #     # print("disabling config")
    #     # await self.presence.disable_config()
    #     print("configured")

    def led_update_state(self, state):
        if state == "OFF":
            for s in self.segments:
                s.off()
        elif state == "SAFE":
            for s in self.segments:
                s.safe()
        elif state == "DANGER":
            for s in self.segments:
                s.danger()
        elif state == "EVAC_LEFT":
            for s in self.segments:
                s.evac_left()
        elif state == "EVAC_RIGHT":
            for s in self.segments:
                s.evac_right()

    async def led_update_handler(self):
        # state subscription first so that we don't miss an update between the start of subscriptions and the query
        sub = await self.gql.subscribe({
            "query": led_update_sub,
            "variables": {"id": self.config["id"]}
        })
        result = await self.gql.query({
            "query": led_update_query,
            "variables": {"id": self.config["id"]}
        })
        self.led_update_state(result["data"]["model"]["getDevice"]["ledState"])
        async for s in sub:
            state = s["data"]["ledStateChanged"]
            self.led_update_state(state)

    # async def read_dht_loop(self):
    #     while self.dht:
    #         await asyncio.sleep(5)  # DO NOT MEASURE MORE OFTEN THAN EVERY 2 SECONDS
    #         self.dht.measure()
    #         self.temperature = self.dht.temperature()
    #         self.humidity = self.dht.humidity()

    async def read_misc_loop(self):
    while True:
        await asyncio.sleep(2)
        if self.din:
            self.smokeDetected = self.din.value != self.config.get("AIR_DIN_PIN_INVERT", False)

            # if self.adc:
            #     self.airQuality = self.adc.read_u16() * 3.3 / (65535)

    async def update_sensors_loop(self):
    while True:
        await asyncio.sleep(0.25)
        if self.din:
            self.smokeDetected = self.din.value != self.config.get("AIR_DIN_PIN_INVERT", False)

        readings = {"id": self.config["id"]}
        if self.din:
            readings["smokeDetected"] = self.smokeDetected
        await self.gql.query({
            "query": update_sensors_query,
            "variables": readings
        })
            # if self.adc:
            #     self.airQuality = self.adc.read_u16() * 3.3 / (65535)
            # if self.dht:
            #     self.dht.measure()
            #     self.temperature = self.dht.temperature()
            #     self.humidity = self.dht.humidity()
            
            
            readings = {"id": self.config["id"]}
            # if self.dht:
            #     readings["temperature"] = self.temperature
            #     readings["humidity"] = self.humidity
            if self.din:
                readings["smokeDetected"] = self.smokeDetected
            # if self.adc:
            #     readings["airQuality"] = self.airQuality
            # if self.presence:
            #     readings["occupied"] = self.presence.ticker > 5
            # print(readings)
            await self.gql.query({
                "query": update_sensors_query,
                "variables": readings
            })

    # async def presence_handler(self):
    #     if self.presence:
    #         asyncio.create_task(self.presence.handler())
    #         asyncio.sleep(1)
    #         await self.config_presence()
        
