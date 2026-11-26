[English](README.md) | 日本語

# claude-session-launcher

> **TL;DR** — 複数の Claude Code セッションをまとめて起動し、それぞれに `/remote-control` で接続できるようにするスクリプトです。Linux を再起動したとき(cron の `@reboot`)に、開発用のセッションが自動で立ち上がるようにしたくて作りました。ついでに、セッションに名前を付けて作業ディレクトリを覚え、前の会話に戻れるようにもしています。

> **AI アシスタントへ:** ユーザーのためにこのツールのコマンドを実行する前に、[`docs/ai-setup.md`](docs/ai-setup.md)(https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/docs/ai-setup.md、英語)を読んでください。

`launch_claude` は、名前を付けた複数の [Claude Code](https://code.claude.com/docs) セッションを tmux で起動し、準備ができたら `/remote-control` を自動で送るツールです。指定すれば、[ttyd](https://github.com/tsl0922/ttyd) でブラウザの端末としても公開します。

- セッションに ID(`writer`、`coder` など)を付けると、作業ディレクトリと会話モードを覚える
- `open` で登録して起動し、`start` で登録済みのセッションを起動し直せる
- `autostart` を付けたセッションは、cron の1行で、再起動後に立ち上がる
- `open --once` で、使い捨てのセッションを開ける(登録されず、claude の終了時に tmux のセッションが消える)

用語: 「セッション」と「エージェント」は同じもので、1つの tmux セッションで動く1つの Claude Code を指し、ID で呼びます。「Remote Control」は、動いているセッションを claude.ai やスマホアプリから使えるようにする Claude Code の機能で、`/remote-control` はそれを有効にするコマンドです。

Python の単一ファイルで、標準ライブラリだけを使います。なお、このスクリプトは 100% Claude Code 製です(人間は、仕様を書いて、文句を言う係でした)。

> **警告: ブラウザの端末(ttyd)は、`--with-ttyd` を指定しないかぎり起動しません。起動した場合は、既定では認証がありません。** ポートに接続できる人は、誰でも端末を操作できます。[安全面](#安全面)を読んでください。

## 目次

- [動作環境](#動作環境)
- [インストール](#インストール)
- [使い始め](#使い始め)
- [コマンド](#コマンド)
- [用途別の設定例](#用途別の設定例)
- [設定](#設定)
- [安全面](#安全面)
- [もっと詳しく](#もっと詳しく)
- [未確認の点](#未確認の点)
- [開発](#開発)
- [ライセンス](#ライセンス)

別のページ:

- [リファレンス](docs/reference.ja.md): 全コマンドとオプション、会話モード、autostart の考え方、運用メモ
- [他の方法との比較](docs/comparison.ja.md): 公式の agent view、Remote Control のサーバーモード、サードパーティ製ツール
- [サンプル](examples/): 用途別の設定ファイル

## 動作環境

- `python3` 3.8 以上(標準ライブラリのみ。`pip install` は不要)。Python がない環境では、先に `sudo dnf install python3` や `sudo apt install python3` などが必要な場合があります。
- `tmux`。既定のシェルが POSIX 系(bash、zsh、sh など)であること
- `ttyd`。ブラウザの端末を使う場合(`--with-ttyd`)だけ必要
- Claude Code。ログイン済みであること(ログインしていないセッションは、ログイン画面で止まります)。Remote Control には、API キーではなく、claude.ai のログイン(`claude auth login`)が必要

Linux を対象としています。カーネルのバージョンには依存しないので、上の4つが動けば使えるはずです。これまでに使った環境は、次のとおりです。

- Ubuntu 24.04 LTS
- Ubuntu 26.04 LTS(WSL 上)
- RHEL 9.7

macOS は、動くかもしれませんが**未検証**です。

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
launch_claude open web            # tmux で、新しい会話を起動。"web" として登録される
launch_claude attach web          # 端末を開く(離れるには Ctrl-b d)。claude.ai からも使える
launch_claude list                # 登録済みのものと、起動中のものを見る
launch_claude stop web            # 止める。登録は残る
launch_claude start web           # 保存済みの設定で、もう一度起動する
launch_claude set web --autostart --mode continue   # 再起動後に、最新の会話で立ち上がるようにする
```

続けて、自分の crontab(`crontab -e`)に1行を足します。

```cron
@reboot $HOME/.local/bin/launch_claude start --autostart
```

cron は、ふだんのシェルを使いません。次の点に注意してください。

- `launch_claude` は、上のようにフルパスで書きます。
- `tmux`(と `ttyd`)が、cron の短い `PATH`(ふつう `/usr/bin:/bin`)で見つかる必要があります。別の場所にある場合は、`@reboot` の行の上に `PATH=...` の行を足します。
- シェルの設定ファイルに書いた環境変数(`TTYD_CREDENTIAL`、`REMOTE_CONTROL`、`CLAUDE_CONFIG_DIR`)は、設定されません。これらの値は、[設定ファイル](#設定)に書いてください。
- `claude` は、tmux が起動したシェルに入力されます。cron からの場合、そのシェルはログインシェルとして動く `/bin/sh` で、`~/.bashrc` ではなく `~/.profile` を読みます。`~/.profile` が `claude` のあるディレクトリを `PATH` に入れていれば(Ubuntu は `~/.local/bin` を入れます)、何もする必要はありません。入れていないか、ファイルがない場合(RHEL は `PATH` を `~/.bashrc` に書きます)は、そのディレクトリを含む `PATH=...` の行を `@reboot` の行の上に足します。シェルはこの `PATH` を引き継ぎます。

### ブラウザの端末

```bash
launch_claude open --with-ttyd web      # 新しいエージェント: ttyd でも公開する。URL が表示される
launch_claude set web --with-ttyd       # 登録済みのエージェント: 次の起動から
launch_claude ttyd web                  # 起動中のエージェント: "ttyd web --off" か "stop" まで
```

7700〜7799 の空きポートを選んで保存するので、URL は変わりません。設定を変えないかぎり、端末は、暗号化のない HTTP で、すべてのネットワークインターフェースに、パスワードなしで開きます。先に[安全面](#安全面)を読んでください。

### 初回の起動

- 最初に起動する前に、一度ログインしてください(`claude auth login`)。これは、ツールが代わりに行うことはできません。
- 作業ディレクトリは、Claude Code の「信頼済み」として記録されるので、信頼の確認で起動が止まることはありません。
- 起動は、Claude Code の入力待ちを最大60秒待ってから、`/remote-control <id>` を入力します。そのあと Claude Code がダイアログ(Disconnect / Show QR code / Continue)を出します。`Continue` が選ばれていれば、ツールが閉じます。開いたままのときは、`tmux attach -t <id>` で入って `Continue` を選んでください。
- 起動に失敗したときは、画面の最後の数行がメッセージに出ます。続きは `launch_claude attach <id>` で見られます。
- claude.ai のログインは、作者の環境では3〜4週間で切れました。切れると、ログインし直すまで Remote Control がつながりません。

## コマンド

```
launch_claude                          ヘルプを表示して終了(終了コード 1)。何も起動しない
launch_claude help | -h | --help       ヘルプ
launch_claude --version                バージョンを表示
launch_claude open [options] [<id>] [dir]   新規または登録済みを開く。--once 以外は自動で登録
                                       (--with-ttyd を付けなければ、tmux のみ)
launch_claude start <id>...            登録済みの ID を起動
launch_claude start --autostart        autostart=1 の全員を起動
launch_claude <id>                     ショートカット(= start <id>)
launch_claude stop [<id>...]           停止。登録は残す。引数なしは、起動中の全員
                                       (実行したセッション自身は残す。止めるには --stop-own-session)
launch_claude attach [<id>]            起動中のエージェントの tmux セッションに入る(離れるには Ctrl-b d)
                                       ID なしは、起動中が1つだけのとき
launch_claude list [--running|--autostart]
launch_claude ttyd <id> [--port <n>]   起動中のエージェントに ttyd を開く。--off か stop まで
                                       (保存済みの設定は変えない)
launch_claude ttyd <id> --off          閉じる。エージェントは動いたまま
launch_claude add <id> [options]       登録のみ(起動しない)
launch_claude set <id> [options]       保存済みの設定を変更
launch_claude forget <id>              登録を削除
launch_claude completion bash          bash の補完スクリプトを出力
```

ID の形式は `^[A-Za-z0-9][A-Za-z0-9_-]*$` です。次の語は予約されていて、ID には使えません: `all`、`start`、`stop`、`open`、`attach`、`add`、`set`、`forget`、`list`、`ttyd`、`completion`、`help`。

ID は、tmux のセッション、Claude Code の会話、Remote Control のセッションの3つの名前になります。Claude Code はこの名前を claude.ai に表示し、ほかの Claude Code のセッションは、この名前を宛先にしてメッセージを送ります。ID の重複を防ぐのは1台のマシンの中だけなので、複数のマシンで使うときは、マシンの間で重ならない ID を付けてください。

### bash の補完

`~/.bashrc` に次の行を足します。

```bash
eval "$(launch_claude completion bash)"
```

Tab で、コマンド、そのオプション、場面に合う ID を補完します。`attach`、`stop`、`ttyd` のあとは起動中のエージェント、`start` と `open` のあとは停止中のもの、`set` と `forget` のあとは登録済みのすべてです。コマンドを短くしたいときは、その行の下に `alias lc=launch_claude` と `complete -F _launch_claude lc` を足します。

### オプション

| オプション | 使えるコマンド | 意味 |
|---|---|---|
| `--dir <path>` | `open`、`add`、`set` | 作業ディレクトリ。`open` では2番目の引数でも指定できる。既定は、カレントディレクトリ |
| `--with-ttyd` / `--without-ttyd` | `open`、`add`、`set` | 起動のたびにブラウザの端末として公開する / tmux のみ。新しいエージェントの既定は、tmux のみ |
| `--port <n>` | `open`、`add`、`set`、`ttyd` | ttyd のポート。これだけを指定すると `--with-ttyd` の意味になる。`--without-ttyd` と一緒に指定すると、あとの `ttyd <id>` のためにポートを取っておくだけ |
| `--autostart` / `--no-autostart` | `open`(`--autostart` のみ)、`add`、`set` | `start --autostart` で起動するかどうか |
| `--mode new\|resume\|continue` | `add`、`set` | `start` のときの会話。既定は `new` |
| `--resume`、`--continue` / `-c` | `open` | 同じ選択を、その1回の起動にだけ使う。保存済みのモードは変えない |
| `--once` | `open` | 使い捨てのセッション。登録せず、claude の終了時に消える |
| `--claude-config-dir <path>` | `open`、`add`、`set` | このエージェントだけの `CLAUDE_CONFIG_DIR`。別のアカウントを使うときなど |
| `--stop-own-session` | `stop` | コマンドを実行したセッション自身も止める |

### 会話モード

| モード | 会話 |
|---|---|
| `new`(既定) | 起動のたびに、新しい空の会話。再起動後に、前の会話は表示されない |
| `resume` | このツールが、その ID で最後に `new` で始めた会話。選択画面は出ず、名前でも探さない |
| `continue` | 作業ディレクトリの最新の会話(誰が始めたものでも)。そのあと、ID の名前に変える。1つのディレクトリに1つのエージェントで使う |

`open` は、`--resume` も `--continue` も付けなければ、常に新しい会話で起動します。

各コマンドの詳しい説明は、[リファレンス](docs/reference.ja.md)にあります。

## 用途別の設定例

よくある場面ごとの設定例です。説明は、各ファイルのコメントに書いてあります。

| やりたいこと | 元にするファイル |
|---|---|
| 全体設定の全項目を見たい | [`examples/config.example`](examples/config.example) |
| エージェントごとの設定の全項目を見たい | [`examples/agents/example.conf`](examples/agents/example.conf) |
| ほかのユーザーと共用のマシンで使う(ポートの範囲を分ける、ttyd にパスワードを付ける) | [`examples/config.shared-machine`](examples/config.shared-machine) |
| ttyd を、nginx・SSH のポート転送・VPN の後ろに置く(設定は確認済み。プロキシ側の例は、案の段階) | [`examples/config.reverse-proxy`](examples/config.reverse-proxy) |
| ttyd なしで動かして、必要なときだけブラウザの端末を開く | [`examples/agents/tmux-only.conf`](examples/agents/tmux-only.conf) |
| 一部のエージェントで、別の Claude アカウントを使う | [`examples/agents/second-account.conf`](examples/agents/second-account.conf) |

サンプルから始める場合は、次のように取得します(全項目のサンプルは、行のコメントを外すまで動作を変えません)。

```bash
mkdir -p ~/.config/launch_claude
curl -fsSL https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/examples/config.example \
  -o ~/.config/launch_claude/config
```

## 設定

設定ファイルは、なくても動きます。すべて任意です。

| 内容 | 場所 |
|---|---|
| 実行ファイル | `~/.local/bin/launch_claude` |
| 全体設定 | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/config` |
| 登録したエージェント(1つにつき1ファイル) | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/agents/<id>.conf` |
| 実行時の状態(最後の会話、最終起動時刻) | `${XDG_STATE_HOME:-~/.local/state}/launch_claude/` |

全体設定(`config`、セクション `[launch_claude]`):

| キー | 既定 | 意味 |
|---|---|---|
| `claude_config_dir` | なし | 全エージェントに使う `CLAUDE_CONFIG_DIR` |
| `remote_control` | `1` | 起動後に `/remote-control <id>` を送る |
| `port_min` | `7700` | エージェントに ttyd のポートを割り当てるときに探す範囲の先頭。ポートは一度選ぶと保存される |
| `port_max` | `7799` | 探す範囲の末尾 |
| `ttyd_interface` | なし | ttyd が待ち受ける場所(`lo`、インターフェース名、IP アドレス)。なしなら、すべてのインターフェース(ネットワークから届く) |
| `ttyd_credential` | なし | ttyd の basic 認証の `user:password` |
| `ttyd_warning` | `1` | ループバック以外に向けて、パスワードなしで ttyd を起動したときに、警告する |

エージェントごとの設定(`agents/<id>.conf`、セクション `[agent]`)。ふつうは `open` / `add` / `set` が書きます。

| キー | 既定 | 意味 |
|---|---|---|
| `dir` | 必須 | 作業ディレクトリ |
| `ttyd` | `0` | `1`: 起動のたびに ttyd で公開する。`0`: tmux のみ |
| `port` | なし | ttyd のポート。`ttyd = 0` の間も残り、予約済みとして扱う |
| `mode` | `new` | `start` のときの会話: `new`、`resume`、`continue` |
| `autostart` | `0` | `1`: `start --autostart` で起動する |
| `claude_config_dir` | なし | このエージェントだけの `CLAUDE_CONFIG_DIR` |

各キーの詳しい説明、注意点、優先順位は、[`examples/config.example`](examples/config.example) と [`examples/agents/example.conf`](examples/agents/example.conf) のコメントにあります。この表にないキーを書くと、「unknown key」と警告されます(書き間違いに気づけます)。

環境変数 `TTYD_CREDENTIAL`(`ttyd_credential` に対応)と `REMOTE_CONTROL`(`remote_control` に対応)は、ファイルの値より優先されます。

## 安全面

- ttyd を起動するのは、`--with-ttyd`(または `ttyd = 1`)で登録したエージェントと、`ttyd <id>` コマンドだけです。
- **ttyd を起動した場合、設定しないかぎり認証はなく**、すべてのネットワークインターフェースで待ち受けます。ポートに接続できる人は、あなたの権限で端末を操作できます。ポートは、ファイアウォールの内側や、信頼できるネットワークの中だけで開けるか、`ttyd_interface = lo` を設定してください。そのような ttyd を起動したときは、ツールが警告します。
- パスワードを付けるには、環境変数 `TTYD_CREDENTIAL=user:password` か、`config` の `ttyd_credential` を設定します(`config` に書く場合は `chmod 600` にしてください。そうでないと警告が出ます)。この値は `ttyd -c` に渡すため、同じマシンの他のユーザーからプロセス一覧で見えます。また、暗号化のない HTTP での basic 認証は、通信を盗み見られると漏れます。
- 起動のたびに、作業ディレクトリを Claude Code の `.claude.json` に「信頼済み」として記録します。信頼の確認で起動が止まらないようにするためです。これは自動で行われ、止める設定はありません。信頼できるディレクトリだけを登録してください。
- launch_claude に分かるのは、自分が ttyd に渡した設定だけです。ポートを別の方法(リバースプロキシ、SSH のポート転送、VPN)で守る場合は、`ttyd_interface` で、その保護が効く場所だけで ttyd が待ち受けるようにしてください(たとえば、同じマシンのプロキシの後ろなら `lo`)。[`examples/config.reverse-proxy`](examples/config.reverse-proxy) を参照。

## もっと詳しく

- [リファレンス](docs/reference.ja.md): 全コマンドとオプション、会話モード、autostart の考え方、運用メモ
- [他の方法との比較](docs/comparison.ja.md): このツール、公式の agent view、Remote Control のサーバーモード、サードパーティ製ツール
- `launch_claude help` で、使い方の全文が表示されます

## 未確認の点

- このツールで起動したセッションが、`claude agents`(Claude Code の agent view。[比較](docs/comparison.ja.md)を参照)の一覧に載るかどうか
- macOS で動くかどうか

## 開発

ツールを変更するときだけ必要です。グローバルには何も入れないように、[uv](https://docs.astral.sh/uv/) を使います。

```bash
tools/check
```

構文の確認、ruff、テスト(手元の Python と、対応する最も古い Python)をまとめて実行します。すべての結果と、末尾の集計は、`reports/check-report.txt` に書かれます(コミットされません)。

テストだけを実行する場合は、次のとおりです。

```bash
uv run --no-project --with pytest pytest                 # 手元の Python
uv run --no-project --python 3.8 --with pytest pytest    # 対応する最も古い Python
```

各テストが何を確認するかは、[`tests/README.md`](tests/README.md)(英語)に一覧があります。結合テストは、専用の tmux サーバーと、スタブの `claude` を使います。tmux がない環境では、スキップされます。

## ライセンス

[MIT](LICENSE)
