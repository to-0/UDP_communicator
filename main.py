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

# PRE ODOSIELATELA
all_ack = 0
sent_fragments = []
acknowledged_fragments = []
counter = 0
timers = dict()


def create_header(fragment_n, ack, nack, final, text_file, checksum):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    text_file = text_file << 4
    ack = ack << 2
    nack = nack << 1
    f = ack + nack + final
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


# server posiela data
def send_data(server_socket, clientaddr, f, n_fragments, actual_f_size, lock):
    global counter
    global all_ack
    global sent_fragments
    global timers
    # treti fragment bude zly
    faulty = 3
    print("Actual f size", actual_f_size)
    # odosielanie
    while all_ack != n_fragments:
        lock.acquire()
        if counter > n_fragments-1:
            lock.release()
            continue
        data = f.read(actual_f_size)
        checksum = calculate_checksum(data)
        print("counter", counter)
        print("data ", data)
        # print(data)
        fin = 0
        if counter == n_fragments-1:  # posielam posledny paket/fragment/datagram wtf ja neviem ako sa to vola
            print("Poslednyyyyy")
            fin = 1

        head = create_header(counter, 0, 0, fin, checksum)
        if counter == faulty:
            data = b'x' + data[1:]
            faulty = -1
        server_socket.sendto(head + data, clientaddr)
        t = threading.Timer(10, timeout_ack, args=(counter, f, lock))
        timers[counter] = t
        t.start()
        sent_fragments.append(counter)
        counter += 1
        print("-"*30)
        lock.release()
    print("Skoncil som posielanie vraj")


def timeout_ack(frag_number, file_pointer, lock, text_file):
    global counter
    with lock:
        print("Timer runs ", frag_number)
        counter = frag_number
        if text_file == "f":
            file_pointer.seek(frag_number)



# server checkuje ack
def check_ack(server_socket, actual_f_size, f, lock):
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
            timer = timers.get(fragment_number)
            if timer is not None:
                print(f'Timer {fragment_number} found and cancelled')
                timer.cancel()
                timers.pop(fragment_number)

            print("ACK a ack cislo a counter", ack, fragment_number, counter)
            if ack == 1 and fragment_number in sent_fragments:
                sent_fragments.remove(fragment_number)

                all_ack += 1
            # prisiel NACK ziadost ze to chce znova proste
            elif nack == 1 and fragment_number in sent_fragments:
                print(f'posuvam counter teraz je {counter} a bude {fragment_number}')
                counter = fragment_number
                f.seek(counter * actual_f_size)
                sent_fragments.remove(fragment_number)
            print("-"*30)


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
    # toto mam robit pri prijimajucej strane ten bind nie pri vysielajucej
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
    send = threading.Thread(target=send_data, args=(s, address, f, n_fragmetns, actual_f_size, lock))
    check = threading.Thread(target=check_ack, args=(s, actual_f_size, f, lock))

    send.start()
    print("Dobry den")
    check.start()

    threads = [send, check]
    for t in threads:
        t.join()

    print(clientMessage.hex())



# KLIENT
def client_send_flags(client_socket, server_addr):
    final = 0

    while final != 1:
        pass


def receive_data(client_socket, server_addr, f):
    recieved = 0
    correct = 0
    last_written = -1
    buffer = dict()
    while True:
        print("Idem cakat na prijem")
        data, sadress = client_socket.recvfrom(16)
        print("Daco som prijal")
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
        print(f'Recieved {recieved} correct {correct} ')

        if checksum_recieved != checksum_from_data:
            print("Vraj sa nerovnaju")
            nack = 1
        else:
            ack = 1
            print("Tu ")
            print(data)
            # ak som predtym zapisal do suboru o 1 mensi fragment (cize zatial mi chodia dobre)
            if last_written == fragment_number - 1:
                last_written = fragment_number
                f.write(data[HEADER_SIZE:])
                correct += 1
                # a nemam prazdny buffer
                if bool(buffer):
                    vals_to_pop = []
                    for key, value in buffer.items():
                        if last_written + 1 == key:
                            f.write(value)
                            last_written += 1
                            vals_to_pop.append(key)
                    for val in vals_to_pop:
                        buffer.pop(val)

            # ak to je este vacsie ako co som posledne zapisal tak si to ulozim do buffera inac to mam v pici
            elif last_written < fragment_number:
                buffer[fragment_number] = data[HEADER_SIZE:]
                correct += 1
        print(f'Bam ack {ack} a fin {fin}')
        head = create_header(fragment_number, ack, nack, 0, checksum_from_data)
        print(head)
        client_socket.sendto(head, server_addr)
        if ack == 1 and fin == 1 and correct==11: #toto je picovina ale musim skusit....
            print("Zatvaram")
            f.close()
            print("Zatvoril som")
            # TODO tu bude timeout ci keep alive alebo ako sa to vola este
            break


def order_and_write(file, buffer):
    pass


def client():
    cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    task = int(input("Send(1), receive(2) or end -1?\n"))
    while task != -1:
        if task == 2:
            # posielam mu ze halo zacinam komunikaciu
            cs.sendto(bytes(1), (HOST, PORT))
            f = open("output.txt", "wb")
            # POZOR!!! TOTO TU NECHAM IBA AK MI SERVER POSLE ESTE SPRAVU ZE OKE IDEM POSIELAT
            # INAC TO DAM KED TAK PREC LEBO BY MI TO ZHLTLO PRVY FRAGMENT
            data, sadress = cs.recvfrom(FRAGMENT_LENGTH)
            print("Tu som prijal toto ", data)
            send_thread = threading.Thread(target=client_send_flags, args=(cs, sadress))
            check_thread = threading.Thread(target=receive_data, args=(cs, sadress, f))
            check_thread.start()

            check_thread.join()
            task = int(input("Send(1), receive(2) or end -1?\n"))
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
    if text_file == 0:
        type_msg = "t"
    else:
        # asi by som si mal posielat aj nazov suboru?
        mess = s.recv(1024)
        name = mess.decode("utf-8")
        type_msg = "f"
        ft = open("/prijate/"+name, "wb")
    print("Idem pocuvat mno")
    while correct != number_of_fragments:
        data, sender_adress = s.recvfrom(FRAGMENT_LENGTH)
        fragment_number = int(data[0:2].hex(), 16)
        flags = int(data[2:3].hex(), 16)
        fin = flags % 2
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
            if ack == 1 and fin == 1 and correct == number_of_fragments:
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
    number_of_fragments = math.ceil(size / (FRAGMENT_LENGTH - HEADER_SIZE))
    actual_fragment_size = FRAGMENT_LENGTH - HEADER_SIZE

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    lock = threading.Lock()
    send = threading.Thread(target=send_data_test, args=(s, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size))
    send.start()
    check = threading.Thread(target=check_ack_test, args=(s, text_or_file, lock, actual_fragment_size, f))
    check.start()


def send_data_test(s, dest, ft, t_or_f, lock, number_of_fragments, actual_fragment_size):
    faulty = 3

    # tu poslat asi hlavicku iba na zaciatok ale nechce sa mi teraz
    b = 0
    print("Number of fragments ", number_of_fragments)
    if t_or_f == "f":
        type_message = 1
        head = create_header(0,0,0,0,1,0)
    else:
        type_message = 0
        head = create_header(0,0,0,0,0,0)
    n_copy = number_of_fragments
    while n_copy != 0:
        n_copy >>=8
        b+=1

    s.sendto(head+number_of_fragments.to_bytes(b, "big"), dest)
    if t_or_f == "f":
        s.sendto(ft.name, dest)
    global all_ack
    global counter
    while all_ack != number_of_fragments:
        lock.acquire()
        if counter > number_of_fragments - 1:
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
        if counter == faulty:
            data = b'x' + data[1:]
            faulty = -1
        print("Dlzka",len(head+data))
        s.sendto(head + data, dest)
        t = threading.Timer(10, timeout_ack, args=(counter, ft, lock, t_or_f))
        timers[counter] = t
        t.start()
        sent_fragments.append(counter)
        counter += 1
        print("-" * 30)
        lock.release()
# kontrolujem ci prislo ack alebo nack
def check_ack_test(s, t_or_f, lock, actual_f_size, ft):
    global all_ack
    global counter
    # TODO zmenit podmienku
    while True:
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
            if ack == 1 and fragment_number in sent_fragments:
                sent_fragments.remove(fragment_number)

                all_ack += 1
            # prisiel NACK ziadost ze to chce znova proste
            elif nack == 1 and fragment_number in sent_fragments:
                if t_or_f == "f":
                    ft.seek(counter * actual_f_size)
                counter = fragment_number
                print(f'posuvam counter teraz je {counter} a bude {fragment_number}')
                sent_fragments.remove(fragment_number)
            print("-"*30)

def timeout_ack_test(frag_number, ft, lock, t_f):
    global counter
    with lock:
        print("Timer runs ", frag_number)
        counter = frag_number
        if t_f == "f":
            ft.seek(frag_number)

if __name__ == '__main__':
    # create_header(80, 1, 0, 0, 2, 3)
    choice = int(input("Sender (1) or reciever (2)?"))
    if choice == 1:
        sender()
        #server()
    else:
        receiver()
        #client()
