import binascii
import socket
import os
import math
import sys
import threading

HEADER_SIZE = 5  # v bajtoch
HOST = '127.0.0.1'
PORT = 1234
FRAGMENT_LENGTH = 16  # v bajtoch
# ===================================================================
# cislo datagramu |||||||||| flagy |||||||| checksum ||||||| length  zatial nevyuzivam ||||||
#  2B najprv                 1B              2B               3B
# =======================================================================
#
#

#PRE SERVER
all_ack = 0
sent_fragments = []
acknowledged_fragments = []
counter = 0

def create_header(fragment_n, ack, nack, final, checksum):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    ack = ack << 2
    nack = nack << 1
    f = ack + nack + final
    #print(f)
    f = f.to_bytes(1, byteorder="big")
    #print(f)
    flags = int(f.hex(), 16)
    #print("Po citani akoze", flags)
    checksum = checksum.to_bytes(2, byteorder="big")
    head = fragment_n + f + checksum
    return head


def read_header(header):
    fragment_number = int(header[0:2].hex(), 16)
    flags = int(header[2:3].hex())
    ack = flags >> 2
    nack = flags >> 1
    final = flags % 2
    checksum = int(header[3:5].hex(), 16)
    return [fragment_number, ack, nack, final, checksum]


def calculate_checksum(data):
    #print("Data v checksume ",data)
    checksum = 0
    i = 1
    #print(type(data))
    # z nejakeho dovodu sa to zmeni rovno na int ked iterujem nvm
    for byte in data:
        #print(byte)
        checksum += byte * i
        i += 1
    return checksum


# server posiela data
def server_send_data(server_socket, clientaddr, f, n_fragments, actual_f_size, lock):
    global counter
    global all_ack
    global sent_fragments
    # treti fragment bude zly
    faulty = 3
    print("Actual f size", actual_f_size)
    # odosielanie
    while all_ack != n_fragments:
        lock.acquire()
        if counter > n_fragments:
            lock.release()
            continue
        data = f.read(actual_f_size)
        checksum = calculate_checksum(data)
        print("counter", counter)
        print("data ", data)
        # print(data)
        fin =0
        if counter+1 == n_fragments: # posielam posledny paket/fragment/datagram wtf ja neviem ako sa to vola
            print("Poslednyyyyy")
            fin = 1

        head = create_header(counter, 0, 0, fin, checksum)
        if counter == faulty:
            data = b'x' + data[1:]
            faulty = 0
            print("Retard ", len(data))
        server_socket.sendto(head + data, clientaddr)
        sent_fragments.append(counter)
        counter += 1
        lock.release()
    print("Skoncil som posielanie vraj")



# server checkuje ack
def check_ack(server_socket, actual_f_size, f, lock):
    ack_number = 0
    global all_ack
    global counter
    global sent_fragments
    while True:
        clientMessage, address = server_socket.recvfrom(HEADER_SIZE)
        items = read_header(clientMessage)
        ack = items[1]
        nack = items[2]
        fragment_number = items[0]


        with lock:
            # dosiel mi ack na nejaky odoslany fragment
            print("ACK a ack cislo a counter", ack, fragment_number, counter)
            if ack == 1 and fragment_number in sent_fragments:
                sent_fragments.remove(fragment_number)
                all_ack += 1
            # prisiel NACK ziadost ze to chce znova proste
            elif nack == 1 and fragment_number in sent_fragments:
                print(f'posuvam counter teraz je {counter} a bude {fragment_number}')
                counter = fragment_number
                f.seek(counter*actual_f_size)
                sent_fragments.remove(fragment_number)


def server():
    global all_ack
    f = open("test_input.txt", "rb")
    size = os.path.getsize("test_input.txt")
    print("File size", size)
    # kolko fragmentov budem potrebovat na tento subor
    n_fragmetns = math.ceil(size / (FRAGMENT_LENGTH - HEADER_SIZE))
    print(n_fragmetns)
    # skutocna dlzka fragmentu do ktorej pojdu data
    actual_f_size = FRAGMENT_LENGTH - HEADER_SIZE

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    # zaciname komunikaciu cakame na to nez sa pripoji prvy krat klient aby sme mu mohli zacat posielat
    clientMessage, address = s.recvfrom(1024)
    # tu mu poslem ze okej priprav sa ak toto neposlem predtym tak klient
    # prvu spravu odignoruje lebo vo funkcii client mam recieve data... som retardovany proste
    # mozem to potom zmenit
    s.sendto(bytes(1), address)
    ack = clientMessage.hex()
    print(bin(int(ack, 16)))
    print(f"Connection from {address}")




    lock = threading.Lock()
    send = threading.Thread(target=server_send_data, args=(s, address, f, n_fragmetns, actual_f_size, lock))
    check = threading.Thread(target=check_ack, args=(s, actual_f_size, f, lock))

    send.start()
    print("Dobry den")
    check.start()

    threads = [send, check]
    for t in threads:
        t.join()

    print(clientMessage.hex())

#KLIENT
def client_send_flags(client_socket, server_addr):
    final = 0

    while final != 1:
        pass

def client_check_data(client_socket, server_addr, f):
    recieved = 0
    correct = 0
    last_written = 0

    while True:
        #print("Idem cakat na prijem")
        data, sadress = client_socket.recvfrom(16)
        #print("Daco som prijal")
        fragment_number = int(data[0:2].hex(), 16)
        flags = int(data[2:3].hex(), 16)
        fin = flags % 2
        print("Fragment ", fragment_number)
        checksum_recieved = int(data[3:5].hex(), 16)
        checksum_from_data = calculate_checksum(data[HEADER_SIZE:])
        recieved += 1
        ack = 0
        nack = 0
        print("Checksum recieved ", checksum_recieved)
        print("Checksum vypocitany ", checksum_from_data)
        if checksum_recieved != checksum_from_data:
            print("Vraj sa nerovnaju")
            nack = 1
        else:
            ack = 1
            print("Tu ")
            print(data)
            correct += 1
            f.write(data[HEADER_SIZE:])
        head = create_header(fragment_number, ack, nack, 0, checksum_from_data)
        client_socket.sendto(head, server_addr)
        if ack == 1 and fin == 1 and recieved == correct:
            print("Zatvaram")
            f.close()
            # TODO tu bude timeout ci keep alive alebo ako sa to vola este
            break



def client():
    cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # posielam mu ze halo zacinam komunikaciu
    cs.sendto(bytes(1), (HOST, PORT))
    last = 0
    f = open("output.txt", "wb")
    # POZOR!!! TOTO TU NECHAM IBA AK MI SERVER POSLE ESTE SPRAVU ZE OKE IDEM POSIELAT
    # INAC TO DAM KED TAK PREC LEBO BY MI TO ZHLTLO PRVY FRAGMENT
    data, sadress = cs.recvfrom(FRAGMENT_LENGTH)
    print("Tu som prijal toto ", data)
    send_thread = threading.Thread(target=client_send_flags, args=(cs, sadress))
    check_thread = threading.Thread(target=client_check_data, args=(cs, sadress, f))
    check_thread.start()

    check_thread.join()


if __name__ == '__main__':
    #create_header(80, 1, 0, 0, 2, 3)
    choice = int(input("Server (1) or client (2)?"))
    if choice == 1:
        server()
    else:
        client()
