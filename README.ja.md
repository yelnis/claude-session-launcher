[English](README.md) | 日本語

# claude-session-launcher

`launch_claude` は、名前を付けた複数の [Claude Code](https://code.claude.com/docs) セッションを tmux で起動するツールです。必要なら [ttyd](https://github.com/tsl0922/ttyd) でブラウザからも操作でき、セッションの準備ができたら `/remote-control` を自動で送ります。

- セッションに ID(`writer`、`coder` など)を付けると、作業ディレクトリ・ポート・会話モードを覚える
- `open` で自動的に登録され、`start` で登録済みのセッションを起動し直せる
- `autostart` を付けたセッションは、cron の1行で、再起動後に立ち上がる
- `open --once` で、終了時に自動で片付く使い捨てのセッションを開ける

Python の単一ファイルで、標準ライブラリだけを使います。

> **警告: ttyd は、既定では認証なしで起動します。** ポートに接続できる人は、誰でも端末を操作できます。[安全面](#安全面)を読んでください。

## 前提

- `python3` 3.8 以上(標準ライブラリのみ。`pip install` は不要)。Python がない環境では、先に `sudo dnf install python3` や `sudo apt install python3` などが必要な場合があります。
- `tmux`
- `ttyd`(tmux のみで使う場合(`--without-ttyd`)は不要)
- Claude Code。Remote Control を使う場合は、`claude auth login` でログイン済みであること

Linux を主な対象としています。macOS は、動くかもしれませんが**未検証**です。

## インストール

```bash
mkdir -p ~/.local/bin
curl -fsSL https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/launch_claude \
  -o ~/.local/bin/launch_claude && chmod +x ~/.local/bin/launch_claude
```

- 更新するときは、同じコマンドをもう一度実行します。
- 安定版を使うときは、URL の `main` をタグ名に置き換えます。
- `~/.local/bin` が `PATH` に入っている必要があります。入っていない場合は、シェルの設定ファイルに次を足します。

  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

## 使い始め

```bash
cd ~/projects/site
launch_claude open web            # 新しい会話で起動。"web" として登録され、ttyd で公開される
launch_claude list                # URL を確認する
launch_claude stop web            # 止める。登録は残る
launch_claude start web           # 保存済みのディレクトリとポートで、もう一度起動する
launch_claude set web --autostart --mode continue   # 再起動後に立ち上がるようにする
```

続けて、crontab(`crontab -e`)に1行を足します。

```cron
@reboot $HOME/.local/bin/launch_claude start --autostart
```

cron の `PATH` は最小限なので、上のようにフルパスで書いてください。

## コマンド

```
launch_claude                          ヘルプを表示して終了(終了コード 1)。何も起動しない
launch_claude help | -h | --help       ヘルプ
launch_claude --version                バージョンを表示
launch_claude start <id>...            登録済みの ID を起動
launch_claude start --autostart        autostart=1 の全員を起動
launch_claude <id>                     ショートカット(= start <id>)
launch_claude open [options] [<id>] [dir]   新規または登録済みを開く。--once 以外は自動で登録
launch_claude add <id> [options]       登録のみ(起動しない)
launch_claude set <id> [options]       保存済みの設定を変更
launch_claude forget <id>              登録を削除
launch_claude stop [<id>...]           停止。登録は残す。引数なしは、起動中の全員
launch_claude list [--running|--autostart]
```

ID の形式は `^[A-Za-z0-9][A-Za-z0-9_-]*$` です。次の語は予約されていて、ID には使えません: `all`、`start`、`stop`、`open`、`add`、`set`、`forget`、`list`、`help`。

### open

```bash
launch_claude open review                  # カレントディレクトリで "review" を登録して起動
launch_claude open review ~/work/repo      # 別のディレクトリで
launch_claude open --resume review         # "review" の最後の会話を再開
launch_claude open -c review               # ディレクトリの最新の会話を続けて、"review" に改名
launch_claude open --without-ttyd review   # tmux のみ。ポートを使わない
launch_claude open --port 7710 review      # ttyd のポートを指定
launch_claude open --once                  # 使い捨てのセッション
launch_claude open --once --with-ttyd tmp  # ttyd と ID を付けた使い捨てのセッション
```

| オプション | 意味 |
|---|---|
| `--resume` | そのエージェントの最後の会話を再開する。その起動だけに効く |
| `--continue`, `-c` | 作業ディレクトリの最新の会話を続けて、`<id>` に改名する。同じディレクトリで別のエージェントが動いているときは、エラーになる |
| `--once` | 常に新しい会話。登録しない。`<id>` を省くと、ID は `once-HHMMSS`。既定で ttyd なし。claude の終了時に tmux と ttyd を片付ける。`--resume`、`--continue`、`--autostart` とは併用できない |
| `--with-ttyd` / `--without-ttyd`(`--no-ttyd`) | ttyd を付ける / tmux のみ |
| `--port <n>` | ttyd のポート(ttyd を付ける)。既定は、`port_min`〜`port_max` の最初の空き |
| `--dir <path>` | 作業ディレクトリ(2番目の位置引数と同じ)。既定は、カレントディレクトリ |
| `--autostart` | `autostart=1` にする |

- 新しい ID は、ディレクトリ・ttyd の有無・ポートとともに登録されます。URL が変わらないように、ポートを保存します。
- 登録済みの ID は、保存済みの設定で起動します。`--dir`、`--port`、`--with-ttyd` / `--without-ttyd`、`--autostart` を指定すると、その値で上書きして保存し、保存したことを表示します。
- `open` は、`--resume` も `--continue` も付けなければ、**新しい会話**で起動します。この2つは、その起動だけに効きます。`start` のときの動きは、`--mode` で保存します(下記)。
- すでに起動中のときは、その旨を表示して、何もしません。

### add / set

```bash
launch_claude add coder --dir ~/work/repo --port 7683 --mode continue --autostart
launch_claude set coder --no-autostart
launch_claude set coder --mode resume
```

オプション: `--dir <path>`、`--port <n>`、`--with-ttyd` / `--without-ttyd`、`--mode new|resume|continue`、`--autostart` / `--no-autostart`。

### start

- 対象を必ず指定します(ID か `--autostart`)。`start` だけだとエラーになります。
- 起動中のものは、スキップします。
- 保存済みのディレクトリが存在しないときは、警告を出してスキップします(`$HOME` には切り替えません)。
- 保存済みの ttyd のポートが空いている必要があります。他のプログラムが使っているポートを、強制的に空けることはしません。

### stop / forget

- `stop <id>...` は、そのエージェントの tmux と ttyd を止めます。`stop` だけだと、このツールが起動したものすべて(`--once` も含む)を止めます。登録は残ります。
- `forget <id>` は、登録と状態を削除します。先に停止してください。

### list

```
ID       STATUS   ACCESS                   DIR      MODE      AUTO  LAST
coder    stopped  -                        ~/repo   continue  *     11/16 18:30
review   stopped  -                        ~/repo   new       -     11/15 10:12
writer   running  http://192.0.2.10:7682   ~/docs   continue  *     11/17 09:00
once-1   running  tmux only (once)         ~/tmp    -         -     11/17 14:00
```

登録済みのエージェントと、起動中の `--once` のセッションを、1つの表で表示します。`--running` は起動中のみ、`--autostart` は `autostart=1` のみを表示します。存在しないディレクトリには `(!)` が付きます。

## 会話モード

| モード | 起動するもの |
|---|---|
| `new`(既定) | ID の名前を付けた新しい会話(`claude --session-id <uuid> --name <id>`)。UUID を記録する |
| `resume` | 記録しておいた会話(`claude --resume <uuid>`)。会話の記録が残っているときだけ。なければ、新しい会話で起動して、その旨を表示する |
| `continue` | 作業ディレクトリの最新の会話(`claude --continue`)。起動後に `/rename <id>` を送る。会話がなければ、新規 |

`resume` が指すのは、その ID でこのツールが最後に `new` モードで始めた会話です。名前で会話を再開することはありません。

## autostart の考え方

プロファイルや `all` はありません。「再起動時に起動する」は、エージェントごとのフラグ1つで表します。

```bash
launch_claude set writer --autostart      # 対象に入れる
launch_claude set writer --no-autostart   # 対象から外す
launch_claude list --autostart            # 起動対象を確認する
launch_claude start --autostart           # 今すぐ起動する(cron が実行するのはこれ)
```

その場かぎりの組み合わせは、`launch_claude start writer coder` のように ID を並べます。`open` で登録しただけのエージェントは、`--autostart` を付けないかぎり `autostart=0` です。

## 保存先

| 内容 | 場所 |
|---|---|
| 実行ファイル | `~/.local/bin/launch_claude` |
| 設定と登録(編集してよいもの) | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/config` と `agents/<id>.conf` |
| 実行時の状態(最後の会話の UUID、最終起動時刻) | `${XDG_STATE_HOME:-~/.local/state}/launch_claude/<id>.state` |

これらのファイルがなくても動きます。設定ファイルは、どちらも INI 形式です。[`examples/config.example`](examples/config.example) と [`examples/agents/example.conf`](examples/agents/example.conf) を参考にしてください。

`config` のキー(セクション `[launch_claude]`):

| キー | 既定 | 意味 |
|---|---|---|
| `claude_config_dir` | なし | `CLAUDE_CONFIG_DIR` に使う値。ここに書いていなければ、環境変数の値を使う。どちらもなければ、Claude Code の既定に任せる |
| `port_min`、`port_max` | `7700`、`7799` | ttyd のポートを自動で選ぶときの範囲 |
| `remote_control` | `1` | 起動後に `/remote-control <id>` を送る。環境変数 `REMOTE_CONTROL=0` が優先される |
| `ttyd_credential` | なし | ttyd の basic 認証の `user:password`。環境変数 `TTYD_CREDENTIAL` が優先される |

`agents/<id>.conf` のキー(セクション `[agent]`): `dir`、`ttyd`(1/0)、`port`、`mode`(`new` / `resume` / `continue`)、`autostart`(1/0)。

## 安全面

- **設定しないかぎり、ttyd は認証なしで起動します。** ポートに接続できる人は、あなたの権限で端末を操作できます。ポートは、ファイアウォールの内側や、信頼できるネットワークの中だけで開けてください。
- パスワードを付けるには、環境変数 `TTYD_CREDENTIAL=user:password` か、`config` の `ttyd_credential` を設定します(`config` に書く場合は `chmod 600` にしてください。そうでないと警告が出ます)。この値は `ttyd -c` に渡すため、同じマシンの他のユーザーからプロセス一覧で見えます。また、暗号化のない HTTP での basic 認証は、通信を盗み見られると漏れます。
- 信頼ダイアログで止まらないように、作業ディレクトリを Claude Code の `.claude.json` に「信頼済み」として記録します。信頼できるディレクトリだけを開いてください。

## ヘルプの文面

```
Usage:
  launch_claude start <id>...            start registered agents
  launch_claude start --autostart        start every agent with autostart=1 (use this from cron @reboot)
  launch_claude <id>                     shortcut for: start <id>
  launch_claude open [options] [<id>] [dir]
                                         open a new or registered agent; registers it unless --once
  launch_claude add <id> [options]       register only (does not start)
  launch_claude set <id> [options]       change saved settings
  launch_claude forget <id>              remove the registration
  launch_claude stop [<id>...]           stop agents, keep registrations; no id = everything running
  launch_claude list [--running|--autostart]
  launch_claude help | -h | --help       show this help
  launch_claude --version                show the version

open options:
  --resume           resume the last conversation of this agent (this launch only)
  --continue, -c     continue the latest conversation in the directory and rename it to <id>
  --once             throwaway: always a new conversation, not registered, auto id (once-HHMMSS)
                     if <id> is omitted, no ttyd by default, cleaned up when claude exits
  --with-ttyd        serve the session with ttyd
  --without-ttyd     tmux only, no port (alias: --no-ttyd)
  --port <n>         ttyd port (implies ttyd; default: first free port in the configured range)
  --dir <path>       work directory (same as the 2nd positional argument; default: current dir)
  --autostart        mark the agent for 'start --autostart'

add / set options:
  --dir <path>  --port <n>  --with-ttyd | --without-ttyd
  --mode new|resume|continue             conversation used by 'start' (default: new)
  --autostart | --no-autostart

Files:
  settings   ${XDG_CONFIG_HOME:-~/.config}/launch_claude/config
  agents     ${XDG_CONFIG_HOME:-~/.config}/launch_claude/agents/<id>.conf
  state      ${XDG_STATE_HOME:-~/.local/state}/launch_claude/

Environment:
  REMOTE_CONTROL=0       do not send /remote-control after start
  TTYD_CREDENTIAL=u:p    protect ttyd with basic auth (ttyd -c)
```

## 他の方法との比較(pros / cons)

2026年11月時点で確認できた範囲です。公式の機能には research preview のものがあり、変わる可能性があります。

### A. このツール(tmux + ttyd + `/remote-control`)

**Pros**
- ID・ポート・作業ディレクトリを固定でき、再起動後も同じ構成に戻せる
- 既存のクローンや worktree の場所で、そのままセッションを動かせる
- ttyd で、ブラウザから端末の画面そのものを操作できる(信頼ダイアログや `/login` などの対話にも対応できる)
- cron の `@reboot` から無人で起動できる
- 小さいので、自分で書き換えやすい

**Cons**
- メンテナンスは自分で行う
- ttyd の認証・ファイアウォール・ポートの管理が必要
- 画面の文言を見て入力待ちを判定しているため、Claude Code の UI が変わると壊れる可能性がある
- ログインの有効期限が切れると、Remote Control が切れる([運用メモ](#運用メモ)を参照)
- tmux / ttyd のコピー・貼り付けに癖がある

### B. 公式の agent view(`claude --bg` / `claude agents`)

裏で動くセッションを、1画面で一覧・操作する機能(research preview)。

**Pros**
- tmux や ttyd なしで、複数のセッションを並列に動かせる
- 状態(実行中 / 入力待ち / 完了 / 失敗 / 停止)が、色とアイコンで一覧できる
- `claude attach` / `logs` / `stop` / `respawn` で操作できる
- `claude agents --json` で、スクリプトから状態を読める
- 編集の前に、独立した git worktree に自動で移るため、並行するセッション同士が同じファイルを書き換えにくい

**Cons**
- research preview で、UI やショートカットが変わる可能性がある
- マシンをシャットダウンすると、実行中のセッションは止まる。再起動しても、自動では立ち上がらない(アタッチや返信で、保存済みの会話から再開する)
- 完了・待機のまま約1時間アタッチされないと、プロセスが止まる(会話は残る。ピン留めで維持できる)
- worktree への自動分離は、「既存のクローンで役割ごとに作業する」構成とは考え方が違う
- 各セッションが、サブスクリプションの利用枠を個別に消費する
- 信頼ダイアログを承認していないディレクトリでは、起動しない
- **未確認:** このツールで起動したセッションが、一覧に載るかどうか

### C. Remote Control のサーバーモード(`claude remote-control`)

1つのプロセスが待ち受けて、claude.ai/code やスマホアプリからの接続ごとにセッションを作る。

**Pros**
- 1プロセスで、複数のセッションを同時に扱える(既定の上限は32)
- `--spawn worktree` で、セッションごとに独立した worktree を使える
- ttyd のポート管理が不要。スマホからも操作できる
- 停止後、約4時間以内なら、`--continue` / `--session-id` で復帰できる

**Cons**
- 端末は待ち受け用で、ローカルから対話するためのものではない
- ID や作業ディレクトリを固定する使い方には向かない(選べるのは `same-dir` か `worktree` か)
- ネットワークが長く切れると、約10分でプロセスが終了する
- `claude setup-token` の長期トークンや `CLAUDE_CODE_OAUTH_TOKEN` では、Remote Control を確立できない。`claude auth login` によるログインが必要
- API キー認証、Bedrock・Vertex・Foundry、`ANTHROPIC_BASE_URL` を別のホストに向けた構成では使えない

### D. 既存のサードパーティ製ツール(Claude Squad、CCManager、ccdeck、claude-tmux など)

**Pros**
- 複数セッションの管理 UI が、すでにある
- 一部は、再起動後に tmux セッションを作り直して、`claude -r` で会話を復元する(ccdeck)
- 自分で保守しなくてよい

**Cons**
- 多くは「新しいタスクなら、新しい worktree と新しいセッション」という流れを前提にしていて、既存のクローンや固定の役割構成とは合いにくい
- ttyd でのブラウザ操作、起動時の `/remote-control` の自動送信、cron `@reboot` での無人起動を、1つで満たすものは見つからなかった
- 外部ツールへの依存が増える

### 使い分けの目安

| やりたいこと | 向いているもの |
|---|---|
| 役割と作業場所を固定して、再起動後も同じ構成で動かしたい | A(このツール) |
| 並列セッションの状態を、1画面で見渡したい | B(agent view)。A との併用は未検証 |
| ブラウザ・スマホから、好きな数のセッションを作りたい | C(サーバーモード) |
| 新しいタスクごとに、worktree 付きで気軽に始めたい | B または D |

## 運用メモ

- ログインの有効期限は、作者の環境では3〜4週間ほどでした。切れると、Remote Control が `OAuth token unavailable` で切断されます。
  - 同じ `CLAUDE_CONFIG_DIR` で、`claude auth login` をやり直します。
  - 動いているセッションが新しい認証情報を読み直さない場合は、`stop` してから `start` します。
- 画面のコピーが難しい場合は、tmux のコピーモードや `tmux capture-pane -p -J` を使います。
- 画面に `? for shortcuts` か `shift+tab to cycle` が出たら、入力待ちになったと判定します(最大60秒)。待ちに失敗したときは、警告に画面の末尾10行が含まれます。この文言が、使っている Claude Code の画面と合っているかを確認してください。
- 起動コマンドは、tmux の既定のシェルに文字として送ります。`VAR=value command` と `||` を使うので、POSIX 系のシェル(bash、zsh など)を想定しています。

## 未確認の点

- このツールで起動したセッションが、`claude agents` の一覧に載るかどうか
- macOS で動くかどうか

## 開発

ツールを変更するときだけ必要です。グローバルには何も入れないように、[uv](https://docs.astral.sh/uv/) を使います。

```bash
python3 -m py_compile launch_claude
uvx ruff check --isolated --target-version py38 --line-length 110 --select E,F,W,B launch_claude tests
uv run --no-project --with pytest pytest                 # 手元の Python
uv run --no-project --python 3.8 --with pytest pytest    # 対応する最も古い Python
```

結合テストは、専用の tmux サーバーと、スタブの `claude` を使います。tmux がない環境では、スキップされます。

## 参考

- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Continue local sessions from any device with Remote Control](https://code.claude.com/docs/en/remote-control)

## ライセンス

[MIT](LICENSE)
