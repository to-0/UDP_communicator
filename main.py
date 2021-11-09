import socket
import os
import math
HEADER_SIZE = 8 # v bajtoch
HOST = '127.0.0.1'
PORT = 1234
FRAGMENT_LENGTH = 16 # v bajtoch
class Header:
    def __init__(self, datagram_number, length, all_datagrams, ack_number,checksum):
        self.datagram_number = datagram_number
        self.length = length
        self.all_datagrams = all_datagrams
        self.ack_number = ack_number
        self.checksum = checksum

def test():
    i = 9
    header = i.to_bytes(1, byteorder="big",signed=True)
    print(header.hex())
    print(int.from_bytes(header, byteorder="big"))
    return header

def create_header(fragment_n, all_fragments, type_o, length):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    all_fragments = all_fragments.to_bytes(2, byteorder="big")
    length = length.to_bytes(2, byteorder="big")
    type_o  = type_o.to_bytes(2, "big")
    head = fragment_n + all_fragments + type_o + length
    print(head)
    print(len(head))
    return head

def server():
    # server
    f = open("test_input.txt", "rb")
    size = os.path.getsize("test_input.txt")
    print("File size",size)
    n_fragmetns = math.ceil(size/(FRAGMENT_LENGTH-HEADER_SIZE))
    print(n_fragmetns)
    actual_f_size = FRAGMENT_LENGTH - HEADER_SIZE
    counter = 1
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    clientMessage, address = s.recvfrom(1024)
    ack = clientMessage.hex()
    print(bin(int(ack, 16)))
    print(f"Connection from {address}")
    print(clientMessage.hex())
    all_ack = 0
    while counter < n_fragmetns and all_ack != n_fragmetns:
        data = f.read(actual_f_size)
        head = create_header(counter, n_fragmetns, 2, actual_f_size)
        s.sendto(head + data, address)
        counter += 1
        # KONTROLA CI MI CHODI ACK
        clientMessage, address = s.recvfrom(HEADER_SIZE)
        ack_number = int(clientMessage[0:2].hex(),16)
        ack_nack = int(clientMessage[4:6].hex(),16)
        print("ACK NUMBER  na ack_TYPe",ack_number,ack_nack)
        if ack_number == counter -1 and ack_nack == 1: # je to ack
            all_ack += 1
        else:
            f.seek(actual_f_size*counter) # skusim znova poslat
            counter -= 1



def client():
    cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ack = test()
    cs.sendto(ack, (HOST, PORT))
    last = 0
    f = open("output.txt", "w")
    while last != 1:
        data, sadress = cs.recvfrom(FRAGMENT_LENGTH)
        print(data)
        fragment_number = int(data[0:2].hex(), 16)
        n = int(data[2:4].hex(), 16)
        print("Fragment ", fragment_number)
        print("all", n)
        head = create_header(fragment_number, 0, 1, 0)
        print("Heead co idem poslat",head)
        cs.sendto(head, sadress)
        f.write(data[HEADER_SIZE:].decode("utf-8"))
        if fragment_number == n-1:
            f.close()
            break


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    choice = int(input("Server (1) or client (2)?"))
    if choice == 1:
        server()
    else:
        client()

