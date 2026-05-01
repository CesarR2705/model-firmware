import asyncio
import binascii
import os
import json
import collections
import time

class WebSocket:
    async def connect(self, host, port, path):
        while 1:
            try:
                self.reader, self.writer = await asyncio.open_connection(host, port)
                break
            except:
                time.sleep(1)
        self.writer.write(
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {binascii.b2a_base64(os.urandom(16)).decode().strip()}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: graphql-transport-ws\r\n"
            f"\r\n".encode())
        await self.writer.drain()
        line = await self.reader.readline()
        if not line.decode().startswith("HTTP/1.1 101"):
            raise ConnectionError
        while line != b"\r\n":
            line = await self.reader.readline()

    async def read(self):
        first_byte = await self.reader.readexactly(1)
        fin_and_opcode = ord(first_byte)
        opcode = fin_and_opcode & 0x0F
        if(opcode == 0x0):
            return None
        # 0x1 = Text frame, 0x2 = Binary frame, 0x9 = Ping, 0xA = Pong
        # send_pong(socket)
        if opcode == 0x8:
            print("Received close frame;")
            # Respond to close with close frame
            # close_frame = bytearray([0x88, 0x00])  # 0x88 is a close frame with no payload
            # socket.write(close_frame)
            return None
        elif opcode == 0x9:
            print("Received ping frame; responding with pong")
            # Respond to ping with pong
            # pong_frame = bytearray([0x8A, 0x00])  # 0x8A is a pong frame with no payload
            # socket.write(pong_frame)
            await self.send_pong()
            return None
        elif opcode == 0xA:
            print("Received pong frame")
            return None
        
        # Read the payload length
        second_byte = ord(await self.reader.readexactly(1))
        masked = (second_byte & 0x80) != 0
        payload_length = second_byte & 0x7F

        if payload_length == 126:
            payload_length = int.from_bytes(await self.reader.readexactly(2), 'big')
        elif payload_length == 127:
            payload_length = int.from_bytes(await self.reader.readexactly(8), 'big')

        # Read the masking key if present
        if masked:
            masking_key = await self.reader.readexactly(4)
        else:
            masking_key = None

        # Read the payload data
        payload = await self.reader.readexactly(payload_length)
        if masked:
            payload = bytearray([payload[i] ^ masking_key[i % 4] for i in range(payload_length)])

        # self.send_pong()
        # Decode only if it's a text frame
        if opcode == 0x1:  # Text frame
            return payload.decode('utf-8')
        else:  # Other opcodes like Binary frame
            return payload  # Return as raw data without decoding
        
    async def write(self, message):
        # Create a WebSocket frame for a text message
        frame = bytearray()

        # Set FIN bit and text frame opcode
        frame.append(0x81)  # 0x80 (FIN) | 0x1 (text)

        # Determine the payload length and set accordingly
        payload_length = len(message)
        if payload_length <= 125:
            frame.append(0x80 | payload_length)  # 0x80 indicates masking
        elif payload_length <= 65535:
            frame.append(0xFE)
            frame.extend(payload_length.to_bytes(2, 'big'))
        else:
            frame.append(0xFF)
            frame.extend(payload_length.to_bytes(8, 'big'))

        # Generate a masking key and mask the payload
        masking_key = os.urandom(4)
        frame.extend(masking_key)

        # Apply mask to the payload
        masked_payload = bytearray([message[i] ^ masking_key[i % 4] for i in range(payload_length)])
        frame.extend(masked_payload)

        # Send the framed message
        self.writer.write(frame)
        await self.writer.drain()

    async def send_ping(self):
        # Create a WebSocket ping frame with a mask
        ping_frame = bytearray([0x89])  # 0x89 (FIN + ping opcode)

        # Ping frame has no payload, so payload length is zero
        payload_length = 0
        ping_frame.append(0x80 | payload_length)  # Mask bit set and length 0

        # Generate a 4-byte masking key
        masking_key = os.urandom(4)
        ping_frame.extend(masking_key)  # Append the masking key to the frame

        # Send the masked ping frame
        self.writer.write(ping_frame)
        await self.writer.drain()
    
    async def send_pong(self):
        # Create a WebSocket pong frame with a mask
        pong_frame = bytearray([0x8A])  # 0x8A (FIN + pong opcode)

        # Pong frame has no payload, so payload length is zero
        payload_length = 0
        pong_frame.append(0x80 | payload_length)  # Mask bit set and length 0

        # Generate a 4-byte masking key
        masking_key = os.urandom(4)
        pong_frame.extend(masking_key)  # Append the masking key to the frame

        # Send the masked pong frame
        self.writer.write(pong_frame)
        await self.writer.drain()

class Subscription:
    def __init__(self, is_sub):
        self.event = asyncio.Event()
        self.data = None
        self.is_sub = is_sub
        self.complete = False
    
    async def wait(self):
        await self.event.wait()
        return self.data
    
class SubIterable:

    """
    Micropython does not support async generators (PEP 525),
    SubIterable is intended to perform the same as:
    
    while True:
        queue = await sub.wait()
    
        while len(queue):
            yield queue.popleft()
    
        if sub.complete:
            break
    
        sub.event.clear()
    
    del self.subscriptions[id]
    return
    """

    def __init__(self, sub, onend):
        self.sub = sub
        self.onend = onend

    def __aiter__(self):
        return self
    
    async def __anext__(self):
        queue = self.sub.data

        if len(queue):
            return queue.popleft()

        if self.sub.complete:
            self.onend()
            raise StopAsyncIteration()

        self.sub.event.clear()
        queue = await self.sub.wait()

        if len(queue):
            return queue.popleft()

        if self.sub.complete:
            self.onend()
            raise StopAsyncIteration()
            
        raise RuntimeError()

class GraphQLWs:
    def __init__(self, ws):
        self.ws = ws
        self.counter = 0
        self.subscriptions = {}
    
    async def connect(self):
        await self.ws.write(json.dumps({"type": "connection_init"}).encode())
        await self.ws.read()

    def next_count(self):
        self.counter += 1
        return str(self.counter)

    async def query(self, payload):
        id = self.next_count()
        sub = Subscription(False)
        self.subscriptions[id] = sub

        message = {
            "id": str(id),
            "type": "subscribe",
            "payload": payload
        }

        await self.ws.write(json.dumps(message).encode())
        data = await sub.wait()
        del self.subscriptions[id]
        return data

    async def subscribe(self, payload):
        id = self.next_count()
        sub = Subscription(True)
        self.subscriptions[id] = sub
        sub.data = collections.deque((), 10)

        message = {
            "id": str(id),
            "type": "subscribe",
            "payload": payload
        }

        await self.ws.write(json.dumps(message).encode())

        return SubIterable(sub, lambda: self.subscriptions.pop(id))
    
    async def handler(self):
        while True:
            message = await self.ws.read()
            if message == None:
                continue
            
            message = json.loads(message)

            if message["type"] == "next":
                sub = self.subscriptions.get(message["id"], None)
                if not sub:
                    continue
                if sub.is_sub:
                    sub.data.append(message["payload"])
                    sub.event.set()
                else:
                    sub.data = message["payload"]
                    sub.event.set()
            elif message["type"] == "error" or message["type"] == "complete":
                sub = self.subscriptions.get(message["id"], None)
                if not sub:
                    continue
                sub.complete = True
                sub.event.set()
            elif message["type"] == "ping":
                await self.ws.write(json.dumps({"type": "pong"}).encode())

