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
# cislo datagramu |||||||||| flagy |||||||| checksum |||||||
#  2B najprv                 1B              2B
# =======================================================================
#
#
MAX_FRAGMENT_SIZE = 1500 - 20 - 8 - 5 # 20 je IPV4 8 je asi UDP a 5 je asi 5

# PRE ODOSIELATELA
all_ack = 0
acknowledged_fragments = []
counter = 0
timers = dict()
WINDOW_SIZE = 4


def create_header(fragment_n, ack, nack, final, text_file, checksum):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    text_file = text_file << 4
    ack = ack << 2
    nack = nack << 1
    f = text_file + ack + nack + final
    # print(f)
    f = f.to_bytes(1, byteorder="big")
    # print(f)
    flags = int(f.hex(), 16)
    # print("Po citani akoze", flags)
    checksum = checksum.to_bytes(2, byteorder="big")
    head = fragment_n + f + checksum
    return head


def read_header(header):
    #print(header, type(header))
    fragment_number = int(header[0:2].hex(), 16)
    #print(f'Fragment number {fragment_number} a henta cast je {header[2:3]}')
    flags = int(header[2:3].hex(), 16)
    ack = flags >> 2
    nack = flags >> 1
    final = flags % 2
    text_file = flags >> 4
    checksum = int(header[3:5].hex(), 16)
    return [fragment_number, ack, nack, final, checksum, text_file]


def calculate_checksum(data):
    checksum = 0
    i = 1
    # z nejakeho dovodu sa to zmeni rovno na int ked iterujem nvm
    for byte in data:
        # print(byte)
        checksum += byte * i
        i += 1
    return checksum

def timeout_ack(frag_number, lock):
    global counter
    with lock:
        print("Timer runs ", frag_number)
        counter = frag_number

def timeout_ack_test(s, dest, frag_number, lock, buffer):
    with lock:
        print("Timer ", frag_number)
        send_missing(buffer,dest,s,frag_number)



##################################################
# TOTO JE JEDEN VELKY TEST POD TYMTO BLOKOM
##################################################
def receiver():
    port = int(input("Zadajte port na ktorom pocuvate\n"))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, port))
    # prva sprava mi hovori ci ide text alebo subor a kolko ramcov
    data = s.recv(1024)
    header = read_header(data)
    text_file = header[5]
    type_msg = ""
    ft = ""
    last_written = -1
    correct = 0
    number_of_fragments = int(data[HEADER_SIZE:].hex(), 16)
    buffer = dict()
    fin = 0
    have_fin = False
    print(header)
    if text_file == 0:
        print("Je to text")
        type_msg = "t"
    else:
        # asi by som si mal posielat aj nazov suboru?
        mess = s.recv(1024)
        print("Je to subor")
        name = mess.decode("utf-8")
        type_msg = "f"
        ft = open("prijate/"+name, "wb+")
    print("Idem pocuvat mno")
    while correct != number_of_fragments:
        data, sender_adress = s.recvfrom(FRAGMENT_LENGTH)
        fragment_number = int(data[0:2].hex(), 16)
        flags = int(data[2:3].hex(), 16)

        print("Fragment ", fragment_number)

        checksum_recieved = int(data[3:5].hex(), 16)
        checksum_from_data = calculate_checksum(data[HEADER_SIZE:])
        ack = 0
        nack = 0

        if checksum_recieved != checksum_from_data:
            print("Vraj sa nerovnaju")
            nack = 1
        else:
            ack = 1
            print(data)
            fin = flags % 2
            if fin == 1:
                have_fin = True
            # ak som predtym zapisal do suboru o 1 mensi fragment (cize zatial mi chodia dobre)
            if last_written == fragment_number - 1:
                last_written = fragment_number
                if type_msg == "f":
                    ft.write(data[HEADER_SIZE:])
                else:
                    ft += data[HEADER_SIZE:].decode('utf-8')
                correct += 1
                # a nemam prazdny buffer
                if bool(buffer):
                    vals_to_pop = []
                    for key, value in buffer.items():
                        if last_written + 1 == key:
                            if type_msg == "f":
                                ft.write(value)
                            else:
                                ft += value.decode('utf-8')
                            last_written += 1
                            vals_to_pop.append(key)
                    for val in vals_to_pop:
                        buffer.pop(val)
            elif last_written < fragment_number:
                buffer[fragment_number] = data[HEADER_SIZE:]
                correct += 1
            # TODO opravit aby som vkladal spravny typ ci text/file teraz tam jebem nulu len tak
        head = create_header(fragment_number, ack, nack, 0, 0, checksum_from_data)
        print(head)
        s.sendto(head, sender_adress)
        if ack == 1 and have_fin and correct == number_of_fragments:
            # este pozriem ci mi nieco nezostalo v bufferi co som nezapisal
            if last_written != number_of_fragments and bool(buffer):
                for key, value in buffer.items():
                    if last_written + 1 == key:
                        if type_msg == "f":
                            ft.write(value)
                        else:
                            ft += value.decode('utf-8')
                        last_written += 1
            print("Zatvaram")
            if type_msg == "f":
                ft.close()
            else:
                print(ft)
            break



def sender():
    ip = input("Zadajte cielovu IP adresu napr 127.0.0.1 \n")
    port = int(input("Zadajte cielovy port napr 1234\n"))
    dest = (ip, port)
    text_or_file = input("Subor (f) alebo text (t)?\n")
    # TODO zadajte velkost fragmentu
    path = ""
    if text_or_file == "f":
        path = input("Zadajte cestu k suboru \n")
        f = open(path, "rb")
    else:
        f = input("Zadajte text ktory chcete odoslat \n")

    if text_or_file == "f":
        size = os.path.getsize(path)
    else:
        size = len(f.encode("utf-8"))
    number_of_fragments = math.ceil(size / FRAGMENT_LENGTH)
    actual_fragment_size = FRAGMENT_LENGTH
    buffer = dict()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(dest)
    lock = threading.Lock()
    send = threading.Thread(target=send_data_test, args=(s, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size, buffer))
    send.start()
    check = threading.Thread(target=check_ack_test, args=(s, text_or_file, lock, actual_fragment_size, f, number_of_fragments, buffer,dest))
    check.start()


def send_data_test(s, dest, ft, t_or_f, lock, number_of_fragments, actual_fragment_size,buffer):
    faulty = 3

    # tu poslat asi hlavicku iba na zaciatok ale nechce sa mi teraz
    b = 0
    print("Number of fragments ", number_of_fragments)
    if t_or_f == "f":
        type_message = 1
        print("Idem posielat subor")
        head = create_header(0, 0, 0, 0, type_message, 0)
    else:
        type_message = 0
        print("Idem posielat text")
        head = create_header(0, 0, 0, 0, type_message, 0)
    n_copy = number_of_fragments
    while n_copy != 0:
        n_copy >>=8
        b+=1

    s.sendto(head+number_of_fragments.to_bytes(b, "big"), dest)
    if t_or_f == "f":
        s.sendto(ft.name.encode("utf-8"), dest)
    global all_ack
    global counter
    while all_ack != number_of_fragments:
        lock.acquire()
        # vyprsal timeout
        if counter in buffer:
            s.sendto(buffer.get(counter), dest)
            lock.release()
        else:
            if counter > number_of_fragments - 1 or len(buffer) == WINDOW_SIZE:
                lock.release()
                continue
            if t_or_f == "f":
                data = ft.read(actual_fragment_size)
            else:
                # takto by to bolo iba keby mam blokovu arq schemu ale kedze sa chcem vracat ako kokot
                # data = ft[:actual_fragment_size]
                start_index = counter*actual_fragment_size
                end_index = start_index+actual_fragment_size
                data = ft[start_index:end_index].encode('utf-8') # to +1 lebo inac by tam ten end_index nebol zahrnuty

            checksum = calculate_checksum(data)
            print("counter", counter)
            print("data ", data)
            # print(data)
            fin = 0
            if counter == number_of_fragments - 1:  # posielam posledny paket/fragment/datagram wtf ja neviem ako sa to vola
                print("Poslednyyyyy")
                fin = 1

            head = create_header(counter, 0, 0, fin, type_message, checksum)
            buffer[counter] = head + data
            if counter == faulty:
                data = b'x' + data[1:]
                faulty = -1
            print("Dlzka", len(head+data))
            s.sendto(head + data, dest)
            t = threading.Timer(10, timeout_ack_test, args=(s, dest, counter, lock, buffer))
            timers[counter] = t
            t.start()
            counter += 1
            print("-" * 30)
            lock.release()
# kontrolujem ci prislo ack alebo nack
def check_ack_test(s, t_or_f, lock, actual_f_size, ft, number_of_fragments, buffer, dest):
    global all_ack
    global counter
    # TODO zmenit podmienku
    while all_ack!=number_of_fragments:
        data = s.recv(HEADER_SIZE)
        items = read_header(data)
        ack = items[1]
        nack = items[2]
        fragment_number = items[0]
        with lock:
            # dosiel mi ack na nejaky odoslany fragment
            timer = timers.get(fragment_number)
            if timer is not None:
                print(f'Timer {fragment_number} found and cancelled')
                timer.cancel()
                timers.pop(fragment_number)

            print("ACK a ack cislo a counter", ack, fragment_number, counter)
            if ack == 1 and fragment_number in buffer:
                buffer.pop(fragment_number)
                all_ack += 1
            # prisiel NACK ziadost ze to chce znova proste
            elif nack == 1 and fragment_number in buffer:
                # if t_or_f == "f":
                #     buffer.get(fragment_number)
                #     ft.seek(counter * actual_f_size)
                print("Idem pustit send missing lebo som dostal nack")
                threading.Thread(target=send_missing, args=(buffer, dest, s, fragment_number)).start()
                # counter = fragment_number
                # print(f'posuvam counter teraz je {counter} a bude {fragment_number}')
                # sent_fragments.remove(fragment_number)
            print("-"*30)


def send_missing(buffer, rec, soc, number):
    print("Send missing")
    data = buffer.get(number)
    soc.sendto(data, rec)



if __name__ == '__main__':
    # create_header(80, 1, 0, 0, 2, 3)
    choice = int(input("Sender (1) or reciever (2)?"))
    if choice == 1:
        sender()
        #server()
    else:
        receiver()
        #client()
