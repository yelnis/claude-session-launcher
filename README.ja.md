[English](README.md) | 日本語

# claude-session-launcher

> **TL;DR** — 複数の Claude Code セッションをまとめて起動し、それぞれに `/remote-control` で接続できるようにするスクリプトです。Linux を再起動したとき(cron の `@reboot`)に、開発用のセッションが自動で立ち上がるようにしたくて作りました。ついでに、セッションに名前を付けて、作業ディレクトリや前回の会話を覚えておく機能も付けています。

`launch_claude` は、名前を付けた複数の [Claude Code](https://code.claude.com/docs) セッションを tmux で起動するツールです。必要なら [ttyd](https://github.com/tsl0922/ttyd) でブラウザからも操作でき、セッションの準備ができたら `/remote-control` を自動で送ります。

- セッションに ID(`writer`、`coder` など)を付けると、作業ディレクトリ・ポート・会話モードを覚える
- `open` で自動的に登録され、`start` で登録済みのセッションを起動し直せる
- `autostart` を付けたセッションは、cron の1行で、再起動後に立ち上がる
- `open --once` で、終了時に自動で片付く使い捨てのセッションを開ける

Python の単一ファイルで、標準ライブラリだけを使います。なお、このスクリプトは 100% Claude Code 製です(人間は、仕様を書いて、文句を言う係でした)。

> **警告: ttyd は、既定では認証なしで起動します。** ポートに接続できる人は、誰でも端末を操作できます。[安全面](#安全面)を読んでください。

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
- `tmux`
- `ttyd`(tmux のみで使う場合(`--without-ttyd`)は不要)
- Claude Code。Remote Control を使う場合は、`claude auth login` でログイン済みであること

Linux を対象としています。カーネルやシェルのバージョンには依存しないので、上の4つが動けば使えるはずです。動作を確認した環境は、次のとおりです。

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
launch_claude open [options] [<id>] [dir]   新規または登録済みを開く。--once 以外は自動で登録
launch_claude start <id>...            登録済みの ID を起動
launch_claude start --autostart        autostart=1 の全員を起動
launch_claude <id>                     ショートカット(= start <id>)
launch_claude stop [<id>...]           停止。登録は残す。引数なしは、起動中の全員
launch_claude list [--running|--autostart]
launch_claude ttyd <id> [--port <n>]   起動中のエージェントに、一時的に ttyd を開く
launch_claude ttyd <id> --off          閉じる。エージェントは動いたまま
launch_claude add <id> [options]       登録のみ(起動しない)
launch_claude set <id> [options]       保存済みの設定を変更
launch_claude forget <id>              登録を削除
```

ID の形式は `^[A-Za-z0-9][A-Za-z0-9_-]*$` です。次の語は予約されていて、ID には使えません: `all`、`start`、`stop`、`open`、`add`、`set`、`forget`、`list`、`ttyd`、`help`。

各コマンドの詳しい説明は、[リファレンス](docs/reference.ja.md)にあります。

## 用途別の設定例

よくある場面ごとの設定例です。説明は、各ファイルのコメントに書いてあります。

| やりたいこと | 元にするファイル |
|---|---|
| 全体設定の全項目を見たい | [`examples/config.example`](examples/config.example) |
| エージェントごとの設定の全項目を見たい | [`examples/agents/example.conf`](examples/agents/example.conf) |
| ほかのユーザーと共用のマシンで使う(ポートの範囲を分ける、ttyd にパスワードを付ける) | [`examples/config.shared-machine`](examples/config.shared-machine) |
| ttyd を、nginx・SSH のポート転送・VPN の後ろに置く | [`examples/config.reverse-proxy`](examples/config.reverse-proxy) |
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
| `port_min` | `7700` | 新しいエージェントのポートを探す範囲の先頭 |
| `port_max` | `7799` | 新しいエージェントのポートを探す範囲の末尾 |
| `ttyd_interface` | なし | ttyd が待ち受ける場所(`lo`、インターフェース名、IP アドレス)。なしなら、すべて |
| `ttyd_credential` | なし | ttyd の basic 認証の `user:password` |
| `ttyd_warning` | `1` | `ttyd <id>` がパスワードなしで ttyd を開いたときに、警告する |

エージェントごとの設定(`agents/<id>.conf`、セクション `[agent]`)。ふつうは `open` / `add` / `set` が書きます。

| キー | 既定 | 意味 |
|---|---|---|
| `dir` | — | 作業ディレクトリ |
| `ttyd` | `0` | `1`: ttyd で公開する。`0`: tmux のみ |
| `port` | なし | ttyd のポート。`ttyd = 0` の間も残り、予約済みとして扱う |
| `mode` | `new` | `start` のときの会話: `new`、`resume`、`continue` |
| `autostart` | `0` | `1`: `start --autostart` で起動する |
| `claude_config_dir` | なし | このエージェントだけの `CLAUDE_CONFIG_DIR` |

各キーの詳しい説明、注意点、優先順位は、[`examples/config.example`](examples/config.example) と [`examples/agents/example.conf`](examples/agents/example.conf) のコメントにあります。この表にないキーを書くと、「unknown key」と警告されます(書き間違いに気づけます)。

## 安全面

- **設定しないかぎり、ttyd は認証なしで起動します。** ポートに接続できる人は、あなたの権限で端末を操作できます。ポートは、ファイアウォールの内側や、信頼できるネットワークの中だけで開けてください。
- パスワードを付けるには、環境変数 `TTYD_CREDENTIAL=user:password` か、`config` の `ttyd_credential` を設定します(`config` に書く場合は `chmod 600` にしてください。そうでないと警告が出ます)。この値は `ttyd -c` に渡すため、同じマシンの他のユーザーからプロセス一覧で見えます。また、暗号化のない HTTP での basic 認証は、通信を盗み見られると漏れます。
- 信頼ダイアログで止まらないように、作業ディレクトリを Claude Code の `.claude.json` に「信頼済み」として記録します。信頼できるディレクトリだけを開いてください。
- launch_claude に分かるのは、自分が ttyd に渡した設定だけです。ポートを別の方法(リバースプロキシ、SSH のポート転送、VPN)で守る場合は、`ttyd_interface` で、ttyd がその経路だけで待ち受けるようにしてください。[`examples/config.reverse-proxy`](examples/config.reverse-proxy) を参照。

## もっと詳しく

- [リファレンス](docs/reference.ja.md): 全コマンドとオプション、会話モード、autostart の考え方、運用メモ
- [他の方法との比較](docs/comparison.ja.md): このツール、公式の agent view、Remote Control のサーバーモード、サードパーティ製ツール
- `launch_claude help` で、使い方の全文が表示されます

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

## ライセンス

[MIT](LICENSE)
