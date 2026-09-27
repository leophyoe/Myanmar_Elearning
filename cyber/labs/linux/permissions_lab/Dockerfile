FROM alpine:3.19

RUN apk add --no-cache bash shadow sudo coreutils openssh openssh-server && \
    ssh-keygen -A && \
    mkdir -p /var/run/sshd && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Create unprivileged student user
RUN useradd -m -s /bin/bash -u 1000 student && \
    echo "student:cyberrange2026" | chpasswd

WORKDIR /home/student

# Setup challenge files
COPY setup.sh /usr/local/bin/setup.sh
RUN chmod +x /usr/local/bin/setup.sh

# Vulnerable target artifact: misconfigured SUID file reader
RUN echo '#!/bin/bash\ncat /var/log/secret_service.log' > /usr/local/bin/check_service && \
    chmod 4755 /usr/local/bin/check_service

USER root
EXPOSE 22

ENTRYPOINT ["/usr/local/bin/setup.sh"]
CMD ["/bin/bash"]

