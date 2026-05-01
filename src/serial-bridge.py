import serial
import requests
import time

SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600
SERVER_URL = 'http://localhost:5000/graphql'

MUTATION = """
mutation($id: Int!, $temperature: Float, $humidity: Float, $smokeDetected: Boolean, $occupied: Boolean) {
    updateSensors(id: $id, sensors: {
        temperature: $temperature,
        humidity: $humidity,
        smokeDetected: $smokeDetected,
        occupied: $occupied
    }) {
        success
        message
    }
}
"""

def parse_values(line):
    return [v.strip() for v in line.split(',')]

def post_sensor(device_id, temperature=None, humidity=None, smoke=None, occupied=None):
    variables = {'id': device_id}
    if temperature is not None:
        variables['temperature'] = temperature
    if humidity is not None:
        variables['humidity'] = humidity
    if smoke is not None:
        variables['smokeDetected'] = smoke
    if occupied is not None:
        variables['occupied'] = occupied
    try:
        r = requests.post(SERVER_URL, json={'query': MUTATION, 'variables': variables}, timeout=2)
        result = r.json()
        if not result.get('data', {}).get('updateSensors', {}).get('success'):
            print(f"[WARN] device {device_id}: {result}")
    except Exception as e:
        print(f"[ERROR] posting device {device_id}: {e}")

def main():
    print(f"Opening serial port {SERIAL_PORT}...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    time.sleep(2)
    print("Connected. Listening for sensor data...")

    flame_values = None
    smoke_values = None
    misc_values  = None

    while True:
        try:
            raw = ser.readline().decode('utf-8', errors='ignore').strip()
            if not raw:
                continue

            print(f"[SERIAL] {raw}")

            if 'flame' in raw.lower():
                data_line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"[SERIAL] {data_line}")
                flame_values = [int(v) for v in parse_values(data_line)]

            elif 'smoke' in raw.lower():
                data_line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"[SERIAL] {data_line}")
                smoke_values = [int(v) for v in parse_values(data_line)]

            elif 'motion' in raw.lower():
                data_line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"[SERIAL] {data_line}")
                misc_values = [v for v in parse_values(data_line)]

            if flame_values and smoke_values and misc_values:
                motion   = int(misc_values[0]) == 1
                humidity = float(misc_values[1])
                temp     = float(misc_values[2])

                for device_id in range(4):
                    i = device_id * 2
                    flame_detected = (flame_values[i] == 0) or (flame_values[i+1] == 0)
                    smoke_detected = (smoke_values[i] > 300) or (smoke_values[i+1] > 300)
                    smoke_combined = flame_detected or smoke_detected

                    if device_id == 0:
                        post_sensor(device_id, temperature=temp, humidity=humidity,
                                    smoke=smoke_combined, occupied=motion)
                    else:
                        post_sensor(device_id, smoke=smoke_combined)

                flame_values = None
                smoke_values = None
                misc_values  = None

        except KeyboardInterrupt:
            print("\nStopping bridge.")
            ser.close()
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(1)

if __name__ == '__main__':
    main()
