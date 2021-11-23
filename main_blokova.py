import socket
import os
import math
import threading
import time

HEADER_SIZE = 6  # v bajtoch
HOST = '127.0.0.1'
PORT = 1234
FRAGMENT_LENGTH = 16  # v bajtoch
# ===================================================================
# cislo datagramu |||||||||| flagy |||||||| checksum |||||||
#  2B najprv                 1B              2B
# =======================================================================
#
#
MAX_FRAGMENT_SIZE = 1500 - 20 - 8 - HEADER_SIZE # 20 je IPV4 8 je asi UDP a 5 je asi 5
keep_alive_var = True
# PRE ODOSIELATELA
all_ack = 0
current = 0
dead = False
repeat = False

# FLAGY __typ(2b)text_f(1b)ack(1b)nack(1b)fin(1b)
#typ: 00 init -> 00 posiela aj receiver response
#     01 end
#     10 data
#     11 keep alive

def create_head_without_checksum(fragment_n, message_type, text_file, ack, nack, final):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    mess_type = int(message_type, 2) << 5
    text_file = text_file << 3
    ack = ack << 2
    nack = nack << 1
    f = mess_type + text_file + ack + nack + final
    f = f.to_bytes(1, byteorder="big")
    head = fragment_n + f
    return head

def create_header(fragment_n, message_type, text_file, ack, nack, final, checksum):
    fragment_n = fragment_n.to_bytes(2, byteorder="big")
    mess_type = int(message_type, 2) << 5
    text_file = text_file << 3
    ack = ack << 2
    nack = nack << 1
    f = mess_type + text_file + ack + nack + final
    # print(f)
    f = f.to_bytes(1, byteorder="big")
    # print(f)
    flags = int(f.hex(), 16)
    # print("Po citani akoze", flags)
    checksum = checksum.to_bytes(3, byteorder="big")
    head = fragment_n + f + checksum
    return head


def read_header(header):
    #print(header, type(header))
    fragment_number = int(header[0:2].hex(), 16)
    flags = int(header[2:3].hex(), 16)
    ack = (flags >> 2) & 1
    nack = (flags >> 1) & 1
    final = flags & 1
    text_file = (flags >> 3) & 1
    message_type = bin((flags >> 5) & 3)
    checksum = int(header[3:6].hex(), 16)
    return [fragment_number, message_type, text_file, ack, nack, final, checksum]


def calculate_checksum(data):
    checksum = 0
    i = 1
    # z nejakeho dovodu sa to zmeni rovno na int ked iterujem nvm
    for byte in data:
        # print(byte)
        checksum += 31*(byte * i)
        i += 1
    return checksum % (2**24)


def timeout_ack(frag_number, lock):
    global current
    global repeat
    with lock:
        print("Timer runs ", frag_number)
        current = frag_number
        repeat = True

def recv_function(s, t_f, number_of_fragments, ft, not_send_fragment):
    last_written = -1
    correct = 0
    print("Som v recv function")
    while correct != number_of_fragments:
        data, sender_adress = s.recvfrom(FRAGMENT_LENGTH + HEADER_SIZE)
        header = read_header(data[:HEADER_SIZE])
        fragment_number = header[0]
        if header[1] != "0b10":
            print(header[1])
            print("We are fucked")
        print("Fragment ", fragment_number)
        print("Checksum", header[-1])
        checksum_recieved = header[-1]
        # nepocitam do toho checksum :)
        checksum_from_data = calculate_checksum(data[0:HEADER_SIZE-3]+data[HEADER_SIZE:])
        print("Checksum from data ", checksum_from_data)
        ack = 0
        nack = 0

        if checksum_recieved != checksum_from_data:
            print("Vraj sa nerovnaju")
            nack = 1
        else:
            ack = 1
            if fragment_number == not_send_fragment:
                not_send_fragment = -1
                print("Nejdem poslat")
                continue
            # ak som predtym zapisal do suboru o 1 mensi fragment (cize zatial mi chodia dobre)
            if last_written == fragment_number - 1:
                last_written = fragment_number
                if t_f == "f":
                    ft.write(data[HEADER_SIZE:])
                else:
                    ft += data[HEADER_SIZE:].decode('utf-8')
                correct += 1
                # a nemam prazdny buffer
        # TODO opravit aby som vkladal spravny typ ci text/file teraz tam jebem nulu len tak
        head = create_header(fragment_number, "0b00", 0, ack, nack, 0, checksum_from_data)
        s.sendto(head, sender_adress)
        print("-" * 30)
        if ack == 1 and  correct == number_of_fragments:
            print("Zatvaram")
            if t_f == "f":
                ft.close()
            else:
                print(ft)
            break



def receiver():
    global current
    global all_ack
    global dead
    while True:
        choice = int(input("Menu:\n 1. Zadajte port\n 2. Ukonci program\n 3. Zmen rolu\n"))
        if choice == 1:
            port = int(input("Zadajte port na ktorom pocuvate\n"))
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((HOST, port))
        elif choice == 2:
            exit(1)
        elif choice == 3:
            break
        # LOOP POKIAL JE NEJAKE SPOJENIE
        first_received = False
        global keep_alive_var
        while not dead:
            if first_received is False:
                s.settimeout(40)
            try:
                # prva sprava mi hovori ci ide text alebo subor a kolko ramcov
                if first_received is False:
                    data = s.recv(FRAGMENT_LENGTH+HEADER_SIZE)
                header = read_header(data)
                if header[1] == '0b00':
                    print("Je to init")
                text_file = header[2]
                ft = ""
                number_of_fragments = int(data[HEADER_SIZE:].hex(), 16)
                print(header)
                if text_file == 0:
                    print("Je to text")
                    type_msg = "t"
                else:
                    # poslem si nazov suboru este
                    mess = s.recv(FRAGMENT_LENGTH+HEADER_SIZE)
                    header = read_header(mess[:HEADER_SIZE])
                    print("Je to subor")
                    if header[2] == "0b01":
                        print("Je to ten init 2")
                    name = mess.decode("utf-8")
                    type_msg = "f"
                    ft = open("prijate/"+name, "wb+")
                print("Idem pocuvat mno")
                faulty_fr = -1
                # samotne prijimanie dat toho suboru
                recv_function(s, type_msg, number_of_fragments, ft, faulty_fr)
                print("Sprava bola prijata")

                print("Teraz keep alive idem mat")
                all_ack = 0
                current = 0
                # prijimanie keep alive a posielanie ack
                ret_value = []
                keep_alive_thread = threading.Thread(target=receive_keep_alive,args=(s,ret_value))
                keep_alive_thread.start()
                next_option = int(input("Vyberte dalsiu akciu:\n1.Pocuvat dalej\n2.Skoncit"))
                if next_option == 2:
                    keep_alive_var = False
                    break
                keep_alive_thread.join()
                if ret_value[0] == -1:
                    print("Spojenie sa ukoncilo")
                    dead = True
                    break
                else:
                    data = ret_value[0]
                    first_received = True
                # keep_alive_end = receive_keep_alive(s)
                # if keep_alive_end == -1:
                #     break
                # else:
                #     print("Prislo init")
                #     data = keep_alive_end
                #     first_received = True

            # skoncil keep alive
            except socket.timeout:
                print("Spojenie sa ukoncilo")
                break

def receive_keep_alive(s,ret_value):
    while True:
        s.settimeout(60)
        try:
            data, sender = s.recvfrom(HEADER_SIZE+FRAGMENT_LENGTH)
            head = read_header(data[:HEADER_SIZE])
            message_type = head[1]
            ack = 0
            print(f'Typ spravy je {message_type}')
            if message_type == "0b11":
                ack = 1
            elif message_type == "0b0":
                print("Prislo tu nieco zvlastne :O")
                ret_value.append(data)
                return data
            response_header = create_header(0, "0b11", 0, ack, 0, 0, 0)
            s.sendto(response_header, sender)
        except socket.timeout:
            print("Spojenie sa prerusilo")
            ret_value.append(-1)
            return -1

# toto robi odosielatel
def keep_alive_after_transmission(s, dest):
    sending_thread = threading.Thread(target=keep_alive, args=(s, dest))
    sending_thread.start()
    global keep_alive_var
    global dead
    while keep_alive_var:
        s.settimeout(60)
        try:
            data = s.recv(FRAGMENT_LENGTH+HEADER_SIZE)
            header = read_header(data[:HEADER_SIZE])
            message_type = header[1]
            ack = header[3]
            if message_type != "0b11" and ack != 1:
                print("Nieco sa pokazilo")
                break
        except socket.timeout:
            print("Spojenie sa prerusilo")
            keep_alive_var = False
            dead = True


def sender():
    ip = input("Zadajte cielovu IP adresu napr 127.0.0.1 \n")
    port = int(input("Zadajte cielovy port napr 1234\n"))
    dest = (ip, port)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    global keep_alive_var
    global current
    global all_ack
    while True:
        text_or_file = input("Subor (f)\nText (t)?\nUkoncit spojenie (e)?\nVymena (s)\n")
        # TODO zadajte velkost fragmentu
        path = ""
        if text_or_file == "f":
            path = input("Zadajte cestu k suboru \n")
            f = open(path, "rb")
        elif text_or_file == "t":
            f = input("Zadajte text ktory chcete odoslat \n")
        elif text_or_file == "e":
            head = create_header(0, "0b00", 0, 0, 0, 1, 0)
            s.sendto(head, dest)
            time.sleep(1)
            break
        elif text_or_file == "s":
            break

        if dead:
            print("Spojenie je prerusene")
            break
        keep_alive_var = False
        current = 0
        all_ack = 0
        if text_or_file == "f":
            size = os.path.getsize(path)
        else:
            size = len(f.encode("utf-8"))
        number_of_fragments = math.ceil(size / FRAGMENT_LENGTH)
        actual_fragment_size = FRAGMENT_LENGTH

        #s.connect(dest)
        lock = threading.Lock()
        timers = dict()
        threads = []
        threads.append(threading.Thread(target=send_data_test,args=(s, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size, timers)))
        threads[-1].start()
        threads.append(threading.Thread(target=check_ack_test, args=(s, lock, number_of_fragments, dest, timers)))
        threads[-1].start()

        for thread in threads:
            thread.join()

        keep_alive_thread = threading.Thread(target=keep_alive_after_transmission, args=(s, dest))
        keep_alive_var = True
        keep_alive_thread.start()

    #send_data_test(s, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size, timers)


def send_data_test(s, dest, ft, t_or_f, lock, number_of_fragments, actual_fragment_size, timers):
    faulty = 3
    b = 0
    global repeat
    print("Number of fragments ", number_of_fragments)
    if t_or_f == "f":
        type_message = 1
        print("Idem posielat subor")
        head = create_header(0, "0b00", type_message, 0, 0, 0, 0)
    else:
        type_message = 0
        print("Idem posielat text")
        head = create_header(0, "0b00", type_message, 0, 0, 0, 0)
    n_copy = number_of_fragments
    while n_copy != 0:
        n_copy >>=8
        b+=1

    s.sendto(head+number_of_fragments.to_bytes(b, "big"), dest)
    if t_or_f == "f":
        s.sendto(ft.name.encode("utf-8"), dest)
    global all_ack
    global current
    buffer = 0
    last = -1
    # posielanie
    while all_ack != number_of_fragments and not dead:
        lock.acquire()
        #print("Som tu v send_Data")
        if (last == current and repeat is False) or current >= number_of_fragments:
            lock.release()
            continue
        if repeat is True:
            head_and_data = buffer
            repeat = False
        else:
            if t_or_f == "f":
                data = ft.read(actual_fragment_size)
            else:
                start_index = current * actual_fragment_size
                end_index = start_index+actual_fragment_size
                # TODO keby to bolo vacsie ten end index ako cele pole nepadne to? skusal som nepadlo... ale mozno by bolo lepsie to fixnut
                data = ft[start_index:end_index].encode('utf-8') # to +1 lebo inac by tam ten end_index nebol zahrnuty
            head_wo_checksum = create_head_without_checksum(current, "0b10", type_message, 0, 0, 0)
            checksum = calculate_checksum(head_wo_checksum+data)
            buffer = head_wo_checksum + checksum.to_bytes(3, "big") + data

            if faulty == current:
                checksum = (checksum +2) % (2**24)
            checksum = checksum.to_bytes(3, "big")
            head_and_data = head_wo_checksum + checksum + data
            print("counter", current)
            print("data ", data)
            if current == number_of_fragments - 1:  # posielam posledny paket/fragment/datagram wtf ja neviem ako sa to vola
                print("Poslednyyyyy")
            #head = create_header(current, "0b10", type_message, 0, 0, fin, checksum)



        print("poslal som")
        s.sendto(head_and_data, dest)
        t = threading.Timer(10, timeout_ack, args=(current, lock))
        timers[current] = t
        t.start()
        print("-" * 30)
        last = current
        lock.release()

# odosielatel posiela keep_alive
def keep_alive(s, dest):
    while keep_alive_var:
        head = create_header(0, "0b11", 0, 0, 0, 0, 0)
        s.sendto(head, dest)
        time.sleep(10)

# kontrolujem ci prislo ack alebo nack
def check_ack_test(s, lock, number_of_fragments, dest, timers):
    global all_ack
    global current
    global repeat
    global dead
    while all_ack!=number_of_fragments:
        s.settimeout(60)
        print("Som v check ack")
        try:
            data = s.recv(HEADER_SIZE)
            print("prislo mi nieco")
            items = read_header(data)
            t_data = items[1]
            # keep alive
            if t_data == "0b11":
                continue
            ack = items[3]
            nack = items[4]
            fragment_number = items[0]
            with lock:
                # dosiel mi ack na nejaky odoslany fragment
                timer = timers.get(fragment_number)
                if timer is not None:
                    print(f'Timer {fragment_number} found and cancelled')
                    timer.cancel()
                    timers.pop(fragment_number)

                print("ACK a ack cislo a counter", ack, fragment_number, current)
                if ack == 1 and fragment_number == current:
                    print("Tu")
                    if current+1 != fragment_number:
                        current += 1
                    all_ack += 1
                # prisiel NACK ziadost ze to chce znova proste
                elif nack == 1 and fragment_number == current:
                    repeat = True
                    current = fragment_number
                print("-"*30)
        except socket.timeout:
            print("Zomrelo to")
    print("Skoncil som ack check")


if __name__ == '__main__':
    # head = create_header(0,"0b11",0,1,1,1,0)
    # read = read_header(head)
    # for item in read:
    #     print(item)

    choice = int(input("Sender (1), reciever (2) or end (3)"))
    while choice != 3:
        if choice == 1:
            sender()
        elif choice == 2:
            receiver()
        choice = int(input("Sender (1) or reciever (2)? or end (3)"))
