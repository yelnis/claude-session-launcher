[English](reference.md) | 日本語 · [README に戻る](../README.ja.md)

# リファレンス

各コマンドの詳しい説明です。目的と使い始めは [README](../README.ja.md)、設定の全項目は [`examples/`](../examples) のコメント付きサンプルを見てください。

## open

```bash
launch_claude open review                  # カレントディレクトリで "review" を登録して起動
launch_claude open review ~/work/repo      # 別のディレクトリで
launch_claude open --resume review         # "review" の最後の会話を再開
launch_claude open -c review               # ディレクトリの最新の会話を続けて、"review" に改名
launch_claude open --with-ttyd review      # ブラウザの端末としても公開する。空きポートを選んで保存する
launch_claude open --port 7710 review      # 同じことを、このポートで
launch_claude open --without-ttyd --port 7710 review   # tmux のみ。ただしポート 7710 を取っておく
launch_claude open --once                  # 使い捨てのセッション
launch_claude open --once --with-ttyd tmp  # ttyd と ID を付けた使い捨てのセッション
```

| オプション | 意味 |
|---|---|
| `--resume` | そのエージェントの最後の会話を再開する。その起動だけに効く |
| `--continue`, `-c` | 作業ディレクトリの最新の会話を続けて、`<id>` に改名する。同じディレクトリで別のエージェントが動いているときは、エラーになる |
| `--once` | 常に新しい会話。登録しない。`<id>` を省くと、ID は `once-HHMMSS`。claude の終了時に tmux と ttyd を片付ける。`--resume`、`--continue`、`--autostart` とは併用できない |
| `--with-ttyd` / `--without-ttyd`(`--no-ttyd`) | 起動のたびに ttyd を付ける / tmux のみ。新しいエージェントの既定は、`add` でも、tmux のみ。`--without-ttyd` でも、保存済みのポートや指定したポートは残るので、あとで同じ URL を使える。ポートがなければ何も保存されず、あとの `ttyd <id>` は最初の空きポートを使う |
| `--port <n>` | ttyd のポート。`--without-ttyd` を付けないかぎり、ttyd を付ける。既定は、`port_min`〜`port_max` の最初の空き |
| `--dir <path>` | 作業ディレクトリ(2番目の位置引数と同じ)。既定は、カレントディレクトリ |
| `--claude-config-dir <path>` | このエージェントだけの `CLAUDE_CONFIG_DIR`。別のアカウントを使うときなど。`default` で指定を外す。[`examples/agents/second-account.conf`](../examples/agents/second-account.conf) を参照 |
| `--autostart` | `autostart=1` にする |

- 新しい ID は、ディレクトリと、ttyd を指定した場合はポートとともに登録されます。URL が変わらないように、ポートを保存します。
- ループバック以外に向けて、ttyd 自身のパスワードなしで ttyd を起動したときは、`open` と `start` も、`ttyd` コマンドと同じ警告を表示します(1回の実行につき1度。[ttyd](#ttyd) を参照)。
- `--mode` は、`open` のオプションではありません。指定すると、`--resume`、`--continue`、`set <id> --mode` を案内するエラーになります。
- 登録済みの ID は、保存済みの設定で起動します。`--dir`、`--port`、`--with-ttyd` / `--without-ttyd`、`--claude-config-dir`、`--autostart` を指定すると、その値で上書きして保存し、保存したことを表示します。
- `open` は、`--resume` も `--continue` も付けなければ、**新しい会話**で起動します。この2つは、その起動だけに効きます。`start` のときの動きは、`--mode` で保存します(下記)。
- すでに起動中のときは、その旨を表示して、何もしません。

## add / set

```bash
launch_claude add coder --dir ~/work/repo --port 7683 --mode continue --autostart
launch_claude set coder --no-autostart
launch_claude set coder --mode resume
```

オプション: `--dir <path>`、`--port <n>`、`--with-ttyd` / `--without-ttyd`、`--claude-config-dir <path>`、`--mode new|resume|continue`、`--autostart` / `--no-autostart`。

## start

- 対象を必ず指定します(ID か `--autostart`)。`start` だけだとエラーになります。
- 起動中のものは、スキップします。
- 保存済みのディレクトリが存在しないときは、警告を出してスキップします(`$HOME` には切り替えません)。
- 保存済みの ttyd のポートが空いている必要があります。他のプログラムが使っているポートを、強制的に空けることはしません。ほかのユーザーと共用するマシンでは、ユーザーごとに `port_min`〜`port_max` の範囲を分けてください([`examples/config.shared-machine`](../examples/config.shared-machine))。

## ttyd

すでに起動中のエージェントに、claude を起動し直さずに ttyd を開きます。閉じることもできます。

```bash
launch_claude ttyd review              # 開く。URL を表示する
launch_claude ttyd review --port 7720  # このポートで開く
launch_claude ttyd review --off        # 閉じる。エージェントは動いたまま
```

- ポートは、`--port` の指定、そのエージェントに保存済みのポート、範囲内の最初の空き、の順で決まります。
- 一時的なものです。保存済みの設定は変えないので、次の `start` は、これまでどおり `ttyd = 0/1` に従います。常に ttyd を付けたい場合は、`set <id> --with-ttyd` を使います。
- 閉じるか、エージェントを止めるまで、開いたままです。ttyd 自身のパスワード(`TTYD_CREDENTIAL` / `ttyd_credential`)なしで、ループバック以外に向けて開いたときは、警告を表示します。ポートの手前にあるプロキシ・VPN・ファイアウォールは、このツールからは見えません。そうした方法で守っている場合は、`ttyd_warning = 0` で警告を消せます。
- `--once` のセッションにも使えます。

「開いた」と表示するのは、このツールが起動した ttyd が、そのポートで実際に待ち受けているときだけです。ほかのプログラムやユーザーがポートを使っている場合は、URL を表示せずにエラーにします。

## attach

- `attach <id>` は、起動中のエージェントの tmux セッションに、今の端末で入ります。離れるには `Ctrl-b d` を押します。エージェントは動いたままです。
- ID を省くと、起動中のセッションが1つだけのときに、それに入ります。複数あるときは、一覧を表示して終わります。
- tmux の中で実行した場合は、tmux の中で tmux を開かずに、表示するセッションを切り替えます。
- 何も起動しません。停止中のエージェントには、`start` のコマンドを案内します。
- 端末が必要です。端末を持たないプログラム(コマンドを実行する AI アシスタントなど)からは、エラーになります。

## completion

`completion bash` は、bash の補完スクリプトを出力します。`~/.bashrc` から `eval "$(launch_claude completion bash)"` で読み込みます。補完するのは、コマンド、オプション、`--mode` の値、`--dir` のあとのディレクトリ、ID です。ID は `launch_claude completion ids running|stopped|registered` を呼んで取得します(1行に1つ出力されます)。対応しているのは bash だけです。

## stop / forget

- `stop <id>...` は、そのエージェントの tmux と ttyd を止めます。`stop --all` は、このツールが起動したものすべて(`--once` も含む)を止めます。登録は残ります。`stop` だけでは何も止めず、起動中のものを一覧にして、ID か `--all` の指定を求めます。`down` は `stop` の短い名前です。
- 止めるのは、このツールが起動したセッションだけです。ツールは、起動したセッションに tmux のオプション `@launch_claude` で目印を付けます。ほかの tmux セッションには触れません。登録済みの ID とたまたま同じ名前のセッションも同じで、名前を指定した場合は警告を出します。
- `stop` を実行したセッション自身は止めません。セッションの中で(人や Claude Code が)入力したコマンドで、そのセッションを誤って終わらせないためです。`stop --all` のときは、ほかを止めて、残したセッションを表示します。そのセッションの ID を指定した `stop <id>` はエラーになり、何も止めません。そのセッションも止めるには、別の端末から実行するか、`--stop-own-session` を付けます。セッションは、tmux が設定する変数 `TMUX` と `TMUX_PANE` で判定します。
- `forget <id>` は、登録と状態を削除します。先に停止してください。

## list

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

ttyd の有無と autostart は別々の設定です。ttyd なし(tmux のみ。既定)のエージェントも、ほかと同じように autostart にできます。

```bash
launch_claude open --autostart myproj   # 新しく登録する場合
launch_claude set myproj --autostart    # 登録済みのものを変える場合
```

この場合、再起動時には tmux のセッションだけが立ち上がり、ポートは使いません。`/remote-control` は ttyd と関係なく送られます。端末を直接見るときは、`tmux attach -t myproj` で入るか、`launch_claude ttyd myproj` で一時的に ttyd を開きます。保存済みのポートは、ttyd が無効の間も残るので、`--with-ttyd` で戻すと同じ URL になります。


## 運用メモ

- ログインの有効期限は、作者の環境では3〜4週間ほどでした。切れると、Remote Control が `OAuth token unavailable` で切断されます。
  - 同じ `CLAUDE_CONFIG_DIR` で、`claude auth login` をやり直します。
  - 動いているセッションが新しい認証情報を読み直さない場合は、`stop` してから `start` します。
- 画面のコピーが難しい場合は、tmux のコピーモードや `tmux capture-pane -p -J` を使います。
- `/remote-control` を送ると、Claude Code が確認のダイアログ(Disconnect / Show QR code / Continue)を開きます。このツールは、`Continue` が選ばれているときだけ Enter を送って閉じます。もしダイアログが残っていたら、`tmux attach -t <id>` で入って、`Continue` を選んでください。
- 画面に `? for shortcuts` か `shift+tab to cycle` が出たら、入力待ちになったと判定します(最大60秒)。待ちに失敗したときは、警告に画面の末尾10行が含まれます。この文言が、使っている Claude Code の画面と合っているかを確認してください。
- 起動コマンドは、tmux の既定のシェルに文字として送ります。`VAR=value command` と `||` を使うので、POSIX 系のシェル(bash、zsh、sh など)を想定しています。
- cron から起動した場合、tmux は既定のシェルを cron の `SHELL`(ふつう `/bin/sh`)から決め、ログインシェルとして動かします。このシェルは、`~/.bashrc` ではなく `~/.profile` を読みます。`claude` は、その結果の `PATH` で見つかる必要があります(cron の `PATH` をシェルが引き継ぎ、そこに `~/.profile` が足した分が加わります)。`claude` のあるディレクトリを足す `~/.profile` がないシステム(RHEL は `PATH` を `~/.bashrc` に書きます)では、そのディレクトリを crontab の `PATH=...` の行に入れます。`tmux` と `ttyd` はツール自身が起動するので、cron の `PATH` にある必要があります。見つからないときは、エラーにそう表示されます。
