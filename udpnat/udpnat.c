/*
 * Copyright (C) 2012 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <stdio.h>
#include <unistd.h>
#include <errno.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include <sys/types.h>
#include <sys/socket.h>

#define PACKET_LEN 512
#define HEAD_LEN 4

#define HEAD_MASTER "MAST"
#define HEAD_SLAVE "SLAV"
#define HEAD_PING "PING"
#define HEAD_REPLY "REPL"


int recvfrom_timeout(int fd, char* buf, struct sockaddr_in target, int timeout_sec) {
    struct sockaddr_in remote;
    socklen_t remote_len = sizeof remote;

    size_t n;

    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(fd, &readfds);

    struct timeval tv;
    tv.tv_sec = timeout_sec;
    tv.tv_usec = 0;

    int res = select(fd + 1, &readfds, NULL, NULL, &tv);
    if (res == -1) {
        printf("Failed select: %s\n", strerror(errno));
        return -1;
    } else if (res == 0) {
        printf("Failed with timeout\n");
        return -1;
    }

    if ((n = recvfrom(fd, buf, PACKET_LEN, 0, &remote, &remote_len)) == -1) {
        printf("Failed recvfrom: %s\n", strerror(errno));
        return -1;
    }

    // TODO: validate incoming remote address

    return n;
}

/* Operate master mode; we control the pings. */
int master(int fd, struct sockaddr_in target) {
    int delays[10] = { 15, 30, 60, 90, 120, 150, 180, 240, 300, 600, -1 };
    int delay;
    int i = 0;

    struct sockaddr_in remote;
    char buf[PACKET_LEN];
    size_t n;

    printf("Started master mode\n");
    while ((delay = delays[i++]) != -1) {
        printf("Sending ping...\n");

        memset(buf, 0, PACKET_LEN);
        memcpy(buf, HEAD_PING, HEAD_LEN);
        memcpy(buf + HEAD_LEN, &delay, sizeof delay);

        if (sendto(fd, buf, PACKET_LEN, 0, &target, sizeof target) != PACKET_LEN) {
            printf("Failed sendto: %s\n", strerror(errno));
            return -1;
        }

        if ((n = recvfrom_timeout(fd, buf, target, 5)) == -1) {
            return -1;
        }
        if (memcmp(buf, HEAD_REPLY, HEAD_LEN) != 0) {
            printf("Failed; expected reply packet\n");
        }

        printf("Received reply!\n");
        printf("Sleeping for just under %d sec...\n", delay);
        sleep(delay - 5);
    }

    return 0;
}

/* Operate in slave mode; we just reply to pings. */
int slave(int fd, struct sockaddr_in target) {
    int timeout = 0;
    char buf[PACKET_LEN];
    size_t n;

    printf("Started slave mode\n");

    while (1) {
        printf("Waiting for ping for just over %d sec...\n", timeout);

        memset(buf, 0, PACKET_LEN);
        if ((n = recvfrom_timeout(fd, buf, target, timeout + 5)) == -1) {
            return -1;
        }

        memcpy(&timeout, buf + HEAD_LEN, sizeof timeout);
        printf("Received ping; sending reply!\n");

        memset(buf, 0, PACKET_LEN);
        memcpy(buf, HEAD_REPLY, HEAD_LEN);

        if (sendto(fd, buf, PACKET_LEN, 0, &target, sizeof target) != PACKET_LEN) {
            printf("Failed sendto: %s\n", strerror(errno));
            return -1;
        }
    }

    return 0;
}

/* Run server that accepts both master and slave connections. */
int server(int port) {
    int fd;
    struct sockaddr_in local;
    struct sockaddr_in remote;
    socklen_t local_len = sizeof local;
    socklen_t remote_len;
    char buf[PACKET_LEN];
    size_t n;

    if ((fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) == -1) {
        printf("Failed socket: %s\n", strerror(errno));
        return -1;
    }

    memset(&local, 0, sizeof local);
    local.sin_family = AF_INET;
    local.sin_port = htons(port);
    local.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(fd, &local, local_len) == -1) {
        printf("Failed bind: %s\n", strerror(errno));
        return -1;
    }

    while (1) {
        printf("Listening on port %d...\n", port);

        remote_len = sizeof remote;
        if ((n = recvfrom(fd, buf, PACKET_LEN, 0, &remote, &remote_len)) == -1) {
            printf("Failed recvfrom: %s\n", strerror(errno));
            return -1;
        }

        printf("Incoming packet from %s:%d\n", inet_ntoa(remote.sin_addr), ntohs(remote.sin_port));

        if (memcmp(buf, HEAD_SLAVE, HEAD_LEN) == 0) {
            master(fd, remote);
        } else if (memcmp(buf, HEAD_MASTER, HEAD_LEN) == 0) {
            slave(fd, remote);
        }
    }

    return 0;
}

/* Run client that connects to given server. */
int client(char* host, int port) {
    int fd;
    struct sockaddr_in local;
    struct sockaddr_in remote;
    char buf[PACKET_LEN];
    size_t n;

    if ((fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) == -1) {
        printf("Failed socket: %s\n", strerror(errno));
        return -1;
    }

    memset(&local, 0, sizeof remote);
    remote.sin_family = AF_INET;
    remote.sin_port = htons(port);
    if (inet_aton(host, &remote.sin_addr) == 0) {
        printf("Failed to convert host");
        return -1;
    }

    printf("Outgoing packet to %s:%d\n", host, port);

    memset(buf, 0, PACKET_LEN);
    memcpy(buf, HEAD_SLAVE, HEAD_LEN);

    if (sendto(fd, buf, PACKET_LEN, 0, &remote, sizeof remote) != PACKET_LEN) {
        printf("Failed sendto: %s\n", strerror(errno));
        return -1;
    }

    slave(fd, remote);

    // TODO: also operate in master mode

    return 0;
}

int main(int argc, char** argv) {
    int c;
    char* host = NULL;
    int port = 0;

    while ((c = getopt(argc, argv, "h:p:")) != -1) {
        switch (c) {
        case 'h':
            host = optarg;
            break;
        case 'p':
            port = atoi(optarg);
            break;
        }
    }

    if (port == 0) {
        printf("udpnat: tool for probing UDP NAT timeouts");
        printf("usage: %s [-h host] -p port\n\n", argv[0]);
        return -1;
    } else if (host == NULL) {
        server(port);
    } else {
        client(host, port);
    }

    return 0;
}
