import socket
import os
import math
import threading
import time

HEADER_SIZE = 7  # v bajtoch
HOST = '127.0.0.1'
PORT = 1234
FRAGMENT_LENGTH = 16  # v bajtoch
# ===================================================================
# cislo datagramu |||||||||| flagy |||||||| checksum |||||||
#  3B                         1B              3B
# =======================================================================
#
#
MAX_FRAGMENT_SIZE = 1500 - 20 - 8 - HEADER_SIZE # 20 je IPV4 8 je asi UDP a 5 je asi 5
# PRE ODOSIELATELA AJ PRIJIMATELA
keep_alive_var = True # pomocna premena, ak je True posiela sa keep alive, ked False keep alive thread sa ukonci
# PRE ODOSIELATELA
all_ack = 0 # zatial spravne prijate spravy, pre ktore prislo ACK
current = 1 # cislo fragmentu, ktory odosielam
dead = False # pomocna premenna, znaci ci je spojenie zive
repeat = False # pomocna premenna, znaci ci mam opakovat odoslanie fragmentu
start_steps = 0 # nadobuda hodnoty 1,2 pri starte a -1 pre switch -2 pre koniec spojenia
# TODO mozno vsetko toto spojit do dict a nazvat to nejako ze shared_memory proste
shared_memory = {"all_ack": 0, "current": 1, "dead": False, "repeat": False, "start_steps": 0}
# FLAGY __typ(2b)text_f(1b)ack(1b)nack(1b)fin(1b)
#typ: 00 init/end ak je aj fin
#     01 switch
#     10 data
#     11 keep alive

# client posiela server prijima


def create_head_without_checksum(fragment_n, message_type, text_file, ack, nack, final):
    fragment_n = fragment_n.to_bytes(3, byteorder="big")
    mess_type = int(message_type, 2) << 5
    text_file = text_file << 3
    ack = ack << 2
    nack = nack << 1
    f = mess_type + text_file + ack + nack + final
    f = f.to_bytes(1, byteorder="big")
    head = fragment_n + f
    return head

def create_header(fragment_n, message_type, text_file, ack, nack, final, checksum):
    fragment_n = fragment_n.to_bytes(3, byteorder="big")
    mess_type = int(message_type, 2) << 5
    text_file = text_file << 3
    ack = ack << 2
    nack = nack << 1
    f = mess_type + text_file + ack + nack + final
    f = f.to_bytes(1, byteorder="big")
    checksum = checksum.to_bytes(3, byteorder="big")
    head = fragment_n + f + checksum
    return head


def read_header(header):
    #print(header, type(header))
    fragment_number = int(header[0:3].hex(), 16)
    flags = int(header[3:4].hex(), 16)
    ack = (flags >> 2) & 1
    nack = (flags >> 1) & 1
    final = flags & 1
    text_file = (flags >> 3) & 1
    message_type = bin((flags >> 5) & 3)
    checksum = int(header[4:7].hex(), 16)
    return {"frag_n": fragment_number, "message_type": message_type, "t_or_f": text_file, "ack": ack, "nack": nack,
            "fin": final, "checksum": checksum}


def calculate_checksum(data):
    checksum = 0
    i = 1
    # z nejakeho dovodu sa to zmeni rovno na int ked iterujem nvm
    for byte in data:
        checksum += 37*(byte * i)
        i += 1
    return checksum % (2**24)


def timeout_ack(frag_number, lock):
    global current
    global repeat
    with lock:
        print("Timer runs ", frag_number)
        current = frag_number
        repeat = True

def recv_function(s, t_f, number_of_fragments, ft,faulty):
    last_written = 0
    correct = 0
    print("Receiving text/file function")
    while correct != number_of_fragments:
        data, sender_adress = s.recvfrom(1500)
        header = read_header(data[:HEADER_SIZE])
        fragment_number = header["frag_n"]
        if header["message_type"] != "0b10":
            print(header["message_type"])
            print("We are fucked")
        print("Fragment ", fragment_number)
        #print(data)
        print("Checksum", header["checksum"])
        checksum_recieved = header["checksum"]
        # nepocitam do toho checksum :)\
        print("I'm going to calculate checksum from ", data[0:HEADER_SIZE-3]+data[HEADER_SIZE:])
        checksum_from_data = calculate_checksum(data[0:HEADER_SIZE-3]+data[HEADER_SIZE:])
        print("Checksum from data ", checksum_from_data)
        ack = 0
        nack = 0
        fin_flag_set = header["fin"]

        if checksum_recieved != checksum_from_data:
            print("Checksums dont match")
            nack = 1
        else:
            ack = 1
            if t_f == "f":
                if fragment_number == last_written +1:
                    ft.write(data[HEADER_SIZE:])
                    last_written = fragment_number
            else:
                if fragment_number == last_written + 1:
                    ft += data[HEADER_SIZE:].decode('utf-8')
                    last_written = fragment_number
            correct += 1
                # a nemam prazdny buffer
        #print("ACK A  NACK", ack, nack)
        head = create_header(fragment_number, "0b10", 0, ack, nack, 0, checksum_from_data)
        if faulty == fragment_number:
            # aby mi neskoncil cyklus skor ako ma lebo prijime napr. paket 6 2x spravne a potom posledny skipne
            correct -= 1
            faulty = -1
            continue
        s.sendto(head, sender_adress)
        print("-" * 30)
        # kedze je to blokova tak mozem skoncit aj tak ze poslem len fin a ak je to spravne tak mam v pici
        if ack == 1 and correct == number_of_fragments and fin_flag_set == 1:
            print("Closing")
            if t_f == "f":
                print(os.path.abspath(ft.name))
                ft.close()
            else:
                print(ft)
            break

def receiver(port):
    global current
    global all_ack
    global dead
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, port))
    while True:
        recv_init(s)

# def receive_keep_alive(s, ret_value):
#     while True:
#         s.settimeout(60)
#         try:
#             data, sender = s.recvfrom(HEADER_SIZE+FRAGMENT_LENGTH)
#             head = read_header(data[:HEADER_SIZE])
#             message_type = head["message_type"]
#             ack = 0
#             print(f'Message type {message_type}')
#             if message_type == "0b11":
#                 ack = 1
#             elif message_type == "0b0":
#                 print("Something weird happened :O")
#                 ret_value.append(data)
#                 return data
#             response_header = create_header(0, "0b11", 0, ack, 0, 0, 0)
#             s.sendto(response_header, sender)
#         except socket.timeout:
#             print("Spojenie sa prerusilo")
#             ret_value.append(-1)
#             return -1

def sender(soc, dest):
    global keep_alive_var
    global current
    global all_ack
    global start_steps
    global dead
    timers = dict()
    dead = False
    lock = threading.Lock()
    print("Destination ", dest)
    listen_thread = threading.Thread(target=check_incoming_sender, args=(soc, lock, timers))
    listen_thread.start()
    print("Starting ")
    # zase pokial to nezomrie no
    while not dead:
        keep_alive_var = True
        keep_thread = threading.Thread(target=keep_alive, args=(soc, dest))
        keep_thread.start()

        text_or_file = input("File (f)\nText (t)?\nClose connection (e)?\nSwitch (s)\n")
        path = ""
        if text_or_file == "f":
            path = input("Path to file \n")
            f = open(path, "rb")
            length = int(input(f'Fragment length 1..{MAX_FRAGMENT_SIZE}\n'))
            if length > MAX_FRAGMENT_SIZE:
                print("Wrong size")
                break
            FRAGMENT_LENGTH = length
        elif text_or_file == "t":
            f = input("Write text you want to send \n")
            length = int(input(f'Fragment length 1..{MAX_FRAGMENT_SIZE}\n'))
            if length > MAX_FRAGMENT_SIZE:
                print("Wrong size")
                break
            FRAGMENT_LENGTH = length
        # ukoncit spojenie
        elif text_or_file == "e":
            head = create_header(0, "0b00", 0, 0, 0, 1, 0)
            soc.sendto(head, dest)
            while True:
                if start_steps == -2:
                    break
            break
        # VYMENA
        elif text_or_file == "s":
            head = create_header(0, "0b01", 0, 0, 0, 0, 0)
            soc.sendto(head, dest)
            keep_alive_var = False
            while True:
                if start_steps == -1:
                    break
            # tu uz mi doslo ack
            dead = True
            # pockam nez sa vypne listen
            listen_thread.join()
            soc.close()
            # predpokladam ze to bude zit
            dead = False
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip = socket.gethostbyname(socket.gethostname())
            print("IP and PORT", ip, dest[1])
            s.bind((ip, dest[1]))
            recv_init(s, dest[1])
            return
        if dead:
            print("Connection closed")
            break
        keep_alive_var = False
        current = 0
        all_ack = 0
        start_steps = 0
        fault = int(input("Select fragment number of which will have a flow -1 if you want no flaws\n"))
        if text_or_file == "f":
            size = os.path.getsize(path)
        else:
            size = len(f.encode("utf-8"))
        number_of_fragments = math.ceil(size / FRAGMENT_LENGTH)
        actual_fragment_size = FRAGMENT_LENGTH
        #s.connect(dest)
        # pockam nez skonci naozaj keep alive
        keep_thread.join()
        # idem posielat
        send_data_test(soc, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size, timers, fault)
        print("Send done")
        start_steps = 0




    #send_data_test(s, dest, f, text_or_file, lock, number_of_fragments, actual_fragment_size, timers)


def send_data_test(s, dest, ft, t_or_f, lock, number_of_fragments, actual_fragment_size, timers, faulty):
    b = 0
    global repeat
    global start_steps
    global dead
    print("Number of fragments ", number_of_fragments)
    n_copy = number_of_fragments
    while n_copy != 0:
        n_copy >>= 8
        b += 1
    if t_or_f == "f":
        type_message = 1
        print("Sending file")
        head = create_header(number_of_fragments, "0b00", type_message, 0, 0, 0, 0)
    else:
        type_message = 0
        print("Sending text")
        head = create_header(number_of_fragments, "0b00", type_message, 0, 0, 0, 0)

    print(head+number_of_fragments.to_bytes(b, "big"))
    try:
        s.sendto(head+number_of_fragments.to_bytes(b, "big"), dest)
    except socket.error:
        print("BREEEEEEAK meeeee")
        s.close()
        dead = True
        return

    if t_or_f == "f":
        head = create_header(0, "0b00", type_message, 0, 0, 0, 0)
        name = os.path.basename(ft.name)
        s.sendto(head+name.encode('utf-8'), dest)
        #print(head+ft.name.encode("utf-8"))
    global all_ack
    global current
    current = 1
    buffer = ""
    last = -1
    # cakam nez mozem
    while not ((t_or_f == "f" and start_steps == 2) or (t_or_f == "t" and start_steps == 1)) and not dead:
        continue

    print("Now I can send some stuff I got all the ack(s)")
    # posielanie
    while all_ack != number_of_fragments and not dead:
        lock.acquire()
        #print("Som tu v send_Data")
        if (last == current and repeat is False) or current > number_of_fragments:
            lock.release()
            continue
        if repeat is True:
            print("Sending again")
            head_and_data = buffer
            repeat = False
        else:
            #zabalim to do bytearray aby som mohol lahko zmenit nejaku hodnotu ked ma byt pokazeny
            if t_or_f == "f":
                data = bytearray(ft.read(actual_fragment_size))
            else:
                start_index = (current-1) * actual_fragment_size #current-1 lebo pocitam ze prvy fragment je 1 no
                end_index = start_index+actual_fragment_size
                data = bytearray(ft[start_index:end_index].encode('utf-8')) # to +1 lebo inac by tam ten end_index nebol zahrnuty
            fin = 0
            if current == number_of_fragments:
                fin = 1
            head_wo_checksum = create_head_without_checksum(current, "0b10", type_message, 0, 0, fin)
            checksum = calculate_checksum(head_wo_checksum+bytes(data))
            #print("Tento checksum idem vyratat z tychto dat", head_wo_checksum+data)
            buffer = head_wo_checksum + checksum.to_bytes(3, "big") + bytes(data)
            if faulty == current:
                checksum = (checksum +2) % (2**24)
                data[0] = (data[0]+1) % 256
                faulty = -1
            checksum = checksum.to_bytes(3, "big")
            head_and_data = head_wo_checksum + checksum + bytes(data)
            print("Fragment", current)
            #print("data ", head_and_data)
            if current == number_of_fragments:  # posielam posledny paket/fragment/datagram wtf ja neviem ako sa to vola
                print("Last fragment")
            #head = create_header(current, "0b10", type_message, 0, 0, fin, checksum)
        s.sendto(head_and_data, dest)
        #print("poslal som")
        t = threading.Timer(10, timeout_ack, args=(current, lock))
        timers[current] = t
        t.start()
        print("-" * 30)
        last = current
        lock.release()

# odosielatel posiela keep_alive
def keep_alive(s, dest):
    global dead
    while keep_alive_var:
        head = create_header(0, "0b11", 0, 0, 0, 0, 0)
        try:
            #print("Sending keep alive to ", dest)
            s.sendto(head, dest)
        except socket.error:
            print("Connection died keep alive failed to send")
            dead = True
            break
        time.sleep(5)

def recv_init(s,port_on_which_i_listen):
    text_file = ""
    ft = ""
    file_name = ""
    number_of_fragments = -1
    print("Hello")
    global dead
    dead = False
    while True:
        s.settimeout(60)
        try:
            print("Waiting")
            data, se = s.recvfrom(1500)
            print(data)
            print(se)
            head = read_header(data)
            message_type = head["message_type"]
            fin = head["fin"]
            print(head)
            if message_type == "0b0" and fin == 0 and text_file == "":
                print("Init")
                text_file = head["t_or_f"]
                number_of_fragments = int(data[HEADER_SIZE:].hex(), 16)
                head_ack = create_header(0, "0b00", text_file, 1, 0, 0, 0)
                faulty = int(input("Which fragment you dont want to acknowledge? -1 if you want to acknowledge everything correctly\n"))
                s.sendto(head_ack, se)
                print(f'Gotta accept {number_of_fragments} fragments')
                # 0 je text
                if text_file == 0:
                    recv_function(s, "t", number_of_fragments, ft, faulty)
                    text_file = ""
                continue
            # je to subor druha sprava po tym co je nad tymto...
            # 1 je subor
            #TODO mozno zmenit aby read header text_file vracalo "t" alebo "f" nie 0 a 1
            if text_file == 1 and message_type == "0b0":
                file_name = data[HEADER_SIZE:].decode("utf-8")
                folder = input("Choose folder where you want to save the file\n")
                try:
                    print(folder+"/"+file_name)
                    ft = open(folder+"/"+file_name, "wb")
                    head_ack = create_header(0, "0b00", text_file, 1, 0, 0, 0)
                    s.sendto(head_ack, se)
                    recv_function(s, "f", number_of_fragments, ft, faulty)
                    text_file = ""
                except IOError:
                    print("Folder doesn't exist")
                    return
            # keep alive
            if message_type == "0b11":
                head = create_header(0, "0b11", 0, 1, 0, 0, 0)
                s.sendto(head, se)
            # koniec spojenia
            if message_type == "0b0" and fin == 1:
                head = create_header(0, "0b00", 0, 1, 0, 1, 0)
                s.sendto(head, se)
                exit(0)
            # switch
            if message_type == "0b1":
                head = create_header(0, "0b01", 0, 1, 0, 0, 0)
                s.sendto(head, se)
                s.close()
                # switch
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # keby som poslal do sender (s, se) tak je tam port z ktoreho mi prichadzali spravy
                time.sleep(2)
                sender(s, (se[0], port_on_which_i_listen))
                return
        except socket.timeout: # or socket.error
            print("Connection died")
            return

def check_incoming_sender(soc, lock, timers):
    global all_ack
    global current
    global repeat
    global dead
    global start_steps
    # predtym tu bolo while True
    while not dead:
        soc.settimeout(60)
        try:
            #print("Idem cakat co ja viem")
            data, who_send_it = soc.recvfrom(1500)
            lock.acquire()
            header = read_header(data)
            message_type = header["message_type"]
            ack = header["ack"]
            nack = header["nack"]
            fin = header["fin"]

            # dosla nejaka odpoved na data
            if message_type == "0b10":
                fragment_number = header["frag_n"]
                print(f'Fragment {fragment_number} ack: {header["ack"]} nack: {header["nack"]}')
                timer = timers.get(fragment_number)
                if timer is not None:
                    print(f'Timer {fragment_number} found and cancelled')
                    timer.cancel()
                    timers.pop(fragment_number)

                if ack == 1 and nack == 0:
                    current += 1
                    all_ack += 1
                if ack == 0 and nack == 1:
                    repeat = True
            # keep alive
            if message_type == "0b11" and ack == 1:
                lock.release()
                continue
            # TODO potvrdilo mi init
            if message_type == "0b0" and ack == 1 and fin == 0:
                start_steps += 1
            # termination signal ack
            if message_type == "0b0" and ack == 1 and fin == 1:
                start_steps = -2
                return
            # TODO switch
            if message_type == "0b1" and ack == 1:
                start_steps = -1
                return
            lock.release()
        except socket.timeout:
            dead = True
            print("Connection died")
            break
        # except socket.error:
        #     print("Nejaky socket error")
        #     soc.close()
        #     dead = True
        #     global keep_alive_var
        #     keep_alive_var = False
        #     break

def main():
    test = create_header(0, "0b00", 0, 0, 0, 0, 25)
    h_test = read_header(test)
    print(h_test["checksum"])
    choice = int(input("Sender (1), reciever (2) or end (3)"))
    while choice != 3:
        if choice == 1:
            ip = input("Select destination IP address, example: 127.0.0.1 \n")
            port = int(input("Select destination port, example: 1234\n"))
            dest = (ip, port)

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender(s, dest)

        elif choice == 2:
            port = int(input("Select port on which you listen example:1234\n"))
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip = socket.gethostbyname(socket.gethostname())
            print("Your IP adress is", ip)
            s.bind((ip, port))
            recv_init(s, port)
        choice = int(input("Sender (1) or reciever (2)? or end (3)"))

if __name__ == '__main__':
    main()