ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}
RUN apt-get update -y
RUN apt-get install -yy --no-install-recommends --no-install-suggests fish tcsh zsh curl ca-certificates
# Nushell is not packaged in Debian, so it comes from the project's own release.
ARG NU_VERSION=0.108.0
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
        amd64) nuarch=x86_64-unknown-linux-gnu ;; \
        arm64) nuarch=aarch64-unknown-linux-gnu ;; \
        *) echo "no nushell build for this architecture, skipping" && exit 0 ;; \
    esac; \
    curl -fsSL "https://github.com/nushell/nushell/releases/download/${NU_VERSION}/nu-${NU_VERSION}-${nuarch}.tar.gz" \
        -o /tmp/nu.tgz; \
    mkdir -p /tmp/nu && tar -xzf /tmp/nu.tgz -C /tmp/nu --strip-components=1; \
    install -m0755 /tmp/nu/nu /usr/local/bin/nu; \
    rm -rf /tmp/nu /tmp/nu.tgz; \
    nu --version
RUN pip install --upgrade pip
COPY . /src
RUN pip install /src
