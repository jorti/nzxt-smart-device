FROM registry.fedoraproject.org/fedora:latest

RUN dnf update -y --setopt=install_weak_deps=False --nodocs && \
    dnf install -y --setopt=install_weak_deps=False --nodocs liquidctl lm_sensors python3-pyyaml && \
    dnf clean all && \
    mkdir /etc/nzxt-smart-device

COPY nzxt-smart-device.py /usr/local/bin
COPY nzxt-smart-device.yaml.EXAMPLE /etc/nzxt-smart-device/nzxt-smart-device.yaml
LABEL maintainer="Juan Orti Alcaine <jortialc@redhat.com>" \
      description="NZXT Smart device manager"
ENTRYPOINT ["/usr/local/bin/nzxt-smart-device.py"]