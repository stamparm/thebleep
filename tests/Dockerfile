ARG PYTHON_VERSION=3
FROM python:${PYTHON_VERSION}
RUN apt-get update -y
RUN apt-get install -yy --no-install-recommends --no-install-suggests fish tcsh zsh mksh ksh93u+m curl ca-certificates
# Nushell is not packaged in Debian, so it comes from the project's own release.
#
# Nothing here may fail the build. This image is what drives bash, zsh, fish and
# tcsh through a real terminal, and the release tarball is a download from
# somebody else's server built against a glibc newer than some `python:3` bases
# carry -- neither of which is a reason for the other four shells to go untested.
# The tests that want Nushell skip when it is not here, and `nu --version` at the
# end of the build says which happened.
ARG NU_VERSION=0.108.0
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) nuarch=x86_64-unknown-linux-gnu ;; \
        arm64) nuarch=aarch64-unknown-linux-gnu ;; \
        *) nuarch='' ;; \
    esac; \
    if [ -n "$nuarch" ] \
            && curl -fsSL --retry 3 \
                "https://github.com/nushell/nushell/releases/download/${NU_VERSION}/nu-${NU_VERSION}-${nuarch}.tar.gz" \
                -o /tmp/nu.tgz \
            && mkdir -p /tmp/nu \
            && tar -xzf /tmp/nu.tgz -C /tmp/nu --strip-components=1 \
            && install -m0755 /tmp/nu/nu /usr/local/bin/nu \
            && nu --version; then \
        echo 'nushell: installed'; \
    else \
        rm -f /usr/local/bin/nu; \
        echo 'nushell: not available here, its tests will skip'; \
    fi; \
    rm -rf /tmp/nu /tmp/nu.tgz
RUN pip install --upgrade pip
COPY . /src
RUN pip install /src
