import asyncio
import digitalio

try:
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError:
    AnalogIn = None

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
    def __init__(self, config, gql, segments, adc=None):
        self.config = config
        self.gql = gql
        self.segments = []
        self.smokeDetected = None
        self.airQuality = None

        for name in config["LED_SEGMENTS"]:
            self.segments.append(segments[name])

        if "AIR_DIN_PIN" in config:
            self.din = digitalio.DigitalInOut(config["AIR_DIN_PIN"])
            self.din.switch_to_input()
        else:
            self.din = None

        if "AIR_ADC_CHANNEL" in config and adc is not None and AnalogIn is not None:
            self.chan = AnalogIn(adc, config["AIR_ADC_CHANNEL"])
        else:
            self.chan = None

        self.r0 = config.get("MQ9_R0", 10.0)
        self.rl = config.get("MQ9_RL", 10.0)
        self.divider = config.get("AIR_ADC_DIVIDER", 2.0)

    def read_gas_ppm(self):
        if self.chan is None:
            return None
        v_sensor = self.chan.voltage * self.divider
        if v_sensor <= 0.01 or v_sensor >= 5.0:
            return None
        rs = (5.0 - v_sensor) / v_sensor * self.rl
        ratio = rs / self.r0
        ppm = 1000.0 * (ratio ** -2.09)
        return max(0.0, min(1000.0, ppm))   # clamp to schema's 0–1000 limit

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

    async def read_misc_loop(self):
        while True:
            await asyncio.sleep(2)
            if self.din:
                self.smokeDetected = self.din.value != self.config.get("AIR_DIN_PIN_INVERT", False)
            if self.chan:
                self.airQuality = self.read_gas_ppm()

    async def update_sensors_loop(self):
        while True:
            await asyncio.sleep(1)     # was 0.25 — 4 Hz floods the subscription
            if self.din:
                self.smokeDetected = self.din.value != self.config.get("AIR_DIN_PIN_INVERT", False)
            if self.chan:
                self.airQuality = self.read_gas_ppm()

            readings = {"id": self.config["id"]}
            if self.din:
                readings["smokeDetected"] = self.smokeDetected
            if self.chan and self.airQuality is not None:
                readings["airQuality"] = round(self.airQuality, 1)
            await self.gql.query({
                "query": update_sensors_query,
                "variables": readings
            })
