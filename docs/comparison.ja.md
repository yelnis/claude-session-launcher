[English](comparison.md) | 日本語 · [README に戻る](../README.ja.md)

# 他の方法との比較(pros / cons)

2026年11月時点で確認できた範囲です。公式の機能には research preview のものがあり、変わる可能性があります。

## A. このツール(tmux + ttyd + `/remote-control`)

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
- ログインの有効期限が切れると、Remote Control が切れる([運用メモ](reference.ja.md#運用メモ)を参照)
- tmux / ttyd のコピー・貼り付けに癖がある

## B. 公式の agent view(`claude --bg` / `claude agents`)

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

## C. Remote Control のサーバーモード(`claude remote-control`)

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

## D. 既存のサードパーティ製ツール(Claude Squad、CCManager、ccdeck、claude-tmux など)

**Pros**
- 複数セッションの管理 UI が、すでにある
- 一部は、再起動後に tmux セッションを作り直して、`claude -r` で会話を復元する(ccdeck)
- 自分で保守しなくてよい

**Cons**
- 多くは「新しいタスクなら、新しい worktree と新しいセッション」という流れを前提にしていて、既存のクローンや固定の役割構成とは合いにくい
- ttyd でのブラウザ操作、起動時の `/remote-control` の自動送信、cron `@reboot` での無人起動を、1つで満たすものは見つからなかった
- 外部ツールへの依存が増える

## 使い分けの目安

| やりたいこと | 向いているもの |
|---|---|
| 役割と作業場所を固定して、再起動後も同じ構成で動かしたい | A(このツール) |
| 並列セッションの状態を、1画面で見渡したい | B(agent view)。A との併用は未検証 |
| ブラウザ・スマホから、好きな数のセッションを作りたい | C(サーバーモード) |
| 新しいタスクごとに、worktree 付きで気軽に始めたい | B または D |

## 参考

- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Continue local sessions from any device with Remote Control](https://code.claude.com/docs/en/remote-control)
