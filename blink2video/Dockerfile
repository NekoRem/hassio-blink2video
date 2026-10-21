# Thin wrapper over the upstream image (nico579dock/blink2video): adds the
# Home Assistant options bridge only. Upstream code is untouched.
FROM nico579dock/blink2video:0.25.0

USER root
ENV BLINK_HOME=/data \
    BLINK_BIND=0.0.0.0 \
    BLINK_NO_BROWSER=1

COPY run.sh /run.sh
RUN chmod +x /run.sh

WORKDIR /app
CMD ["/run.sh"]
