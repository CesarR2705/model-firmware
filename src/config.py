import board

GRAPHQL_HOST = "localhost"
GRAPHQL_PORT = 5000
GRAPHQL_PATH = "/"

# --- ADS1115 ---
ADS1115_ADDRESS = 0x48
ADS1115_GAIN = 1          # ±4.096V full scale

led_pins = [
    {
        "PIN": board.D18,
        "COUNT": 72
    },
]

led_segments = [
    {
        "name": "HALL3",
        "span": 14,
        "reversed": False
    },
    {
        "name": "HALL2",
        "span": 14,
        "reversed": False
    },
        {
        "name": "HALL1",
        "span": 13,
        "reversed": False
    },
        {
        "name": "HALL0",
        "span": 31,
        "reversed": False
    },
]

devices = (
    {
        "id": 0,
        "LED_SEGMENTS": ["HALL0"],
        "AIR_DIN_PIN": board.D24,
        "AIR_DIN_PIN_INVERT": True,
        "AIR_ADC_CHANNEL": 0,
        "AIR_ADC_DIVIDER": 2.0,   # your resistor divider ratio
        "MQ9_RL": 10.0,           # load resistor on the Grove board, kΩ
        "MQ9_R0": 10.0            # clean-air baseline — MUST calibrate, see below
    }, {
        "id": 1,
        "LED_SEGMENTS": ["HALL1"],
    }, {
        "id": 2,
        "LED_SEGMENTS": ["HALL2"],
    }, {
        "id": 3,
        "LED_SEGMENTS": ["HALL3"],
        "AIR_DIN_PIN": board.D23,
        "AIR_DIN_PIN_INVERT": True,
        "AIR_ADC_CHANNEL": 1,
        "AIR_ADC_DIVIDER": 2.0,
        "MQ9_RL": 10.0,
        "MQ9_R0": 10.0
    }
)
