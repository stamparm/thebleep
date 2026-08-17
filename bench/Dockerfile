# Pinned environment for latency benchmarks, so numbers are comparable across
# machines and across months.
#
#   docker build -t thebleep/bench -f bench/Dockerfile --build-arg PYTHON_VERSION=3.11 .
#   docker run --rm --cpuset-cpus=2,3 thebleep/bench
#
# The default command benchmarks this working tree against upstream The Fuck,
# which is only installable up to Python 3.11.
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

RUN apt-get update -y \
    && apt-get install -yy --no-install-recommends --no-install-suggests \
        git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# hyperfine gives better statistics than a hand-rolled loop; the harness falls
# back to its own timer if this download is unavailable at build time.
ARG HYPERFINE_VERSION=1.18.0
RUN set -eu; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in amd64) target=x86_64-unknown-linux-musl ;; \
                    arm64) target=aarch64-unknown-linux-gnu ;; \
                    *) target='' ;; esac; \
    if [ -n "$target" ]; then \
        url="https://github.com/sharkdp/hyperfine/releases/download/v${HYPERFINE_VERSION}/hyperfine-v${HYPERFINE_VERSION}-${target}.tar.gz"; \
        (python -c "import urllib.request,sys; urllib.request.urlretrieve(sys.argv[1], '/tmp/h.tgz')" "$url" \
            && tar -xzf /tmp/h.tgz -C /tmp \
            && mv /tmp/hyperfine-*/hyperfine /usr/local/bin/ \
            && rm -rf /tmp/h.tgz /tmp/hyperfine-*) || echo "hyperfine unavailable, harness will use its own timer"; \
    fi

WORKDIR /src
COPY . /src

RUN ./bench/setup_subjects.sh python /bench-venvs

ENV BENCH_CPU=""
CMD ["sh", "-c", "./bench/bench.py \
    $([ -d /bench-venvs/fuck-* ] && echo --subject fuck=$(echo /bench-venvs/fuck-*/bin/thefuck)) \
    --subject bleep=$(echo /bench-venvs/bleep-*/bin/thebleep) \
    --subject bleep-src=$(echo /bench-venvs/bleep-src-*/bin/thebleep)"]
