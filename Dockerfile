FROM ghcr.io/astral-sh/uv:0.10.12-python3.12-trixie

RUN useradd -m -u 1000 user
RUN mkdir -p /home/user/.cache/uv && chown -R user:user /home/user

ENV HOME=/home/user
WORKDIR $HOME/app
COPY --chown=user . .
RUN mkdir -p $HOME/venv && chown -R user:user $HOME/venv
USER user
RUN uv venv $HOME/venv && . $HOME/venv/bin/activate && uv sync --active --locked

EXPOSE 7860

CMD . $HOME/venv/bin/activate && voila --no-browser notebooks/