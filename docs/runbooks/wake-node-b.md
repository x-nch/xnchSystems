# Runbook — Wake / Sleep Node B

Node B (`xnch-core`, 192.168.50.2) sleeps when idle and is Wake-on-LAN
wakeable from Node A. Sources: `infra/no-k3s/node-a/wake-node-b.sh`,
`start-node-a.sh` flags, [topology](../architecture/topology.md).

## Wake from Node A

```bash
./infra/no-k3s/node-a/wake-node-b.sh          # WoL packet, then wait up to 180s for ping
```

Integrated into bring-up:

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
./start-node-a.sh --wake-node-b --wait-node-b # wake + block until vLLM :8082 answers
```

## Verify awake & serving

```bash
ping -c1 192.168.50.2
curl -sf http://192.168.50.2:8082/health      # vLLM
curl -sf http://192.168.50.2:8000/health      # nexi
```

## Putting it back to sleep

No managed script exists in-repo — use the host's own suspend
(`sudo systemctl suspend` on Node B) after confirming nothing needs it:

- no running workflow steps ([queue check](../guides/operate-hitl.md))
- consolidation timer is a **Node A** job, unaffected
- muse/CLI traffic will fail while asleep; wake on demand

If wake fails: check WoL enabled in BIOS/UEFI and that the last shutdown was a
clean suspend (hard power-off defeats WoL).
