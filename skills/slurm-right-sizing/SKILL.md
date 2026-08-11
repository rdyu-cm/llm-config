---
name: slurm-right-sizing
description: Use before submitting or editing any Slurm allocation (sbatch, salloc, srun, job scripts, job arrays) to compare requested resources against evidence of what the work actually needs, estimate the queue cost of the request, and propose a smaller allocation when the request is oversized and the wait is long.
---

# Slurm Right-Sizing

## Purpose

Decide whether a Slurm request is worth what it will cost in queue time, and propose a
smaller allocation when it is not. This is an advisory workflow: produce a recommendation
and the evidence behind it. Do not submit, requeue, or cancel anything without explicit
user confirmation.

Scope is the allocation itself — CPUs, GPUs, memory, nodes, walltime, partition, QoS.
Debugging a failed job, writing a job script from scratch, or operating the cluster
generally are out of scope.

**Core principle:** an oversized request is only worth shrinking when the reduction
crosses a scheduling boundary. Cutting `--mem` from 64G to 60G on a 1 TB node changes
nothing about when the job starts. Dropping from 2 nodes to 1, from 4 GPUs to 2, or from
the partition's max walltime into the backfill window can change it by hours.

## Never assume the site

Partition names, QoS names, GPU type strings, default memory-per-CPU, per-user caps, and
walltime limits are site-specific. Discover them; never invent them. If a command is
unavailable or returns nothing, say so and state what that leaves unverified rather than
substituting a plausible value.

## Step 1 — Read the request as submitted

Collect every dimension of the ask before judging any of it.

- Parse `#SBATCH` directives from the script, then the command-line flags. **Command-line
  flags override script directives** — judge the effective request, not the file.
- Note what is *implicit*: unset `--mem` inherits `DefMemPerCPU`/`DefMemPerNode`; unset
  `--time` inherits the partition default, which is often the partition maximum.
- For a pending job already in queue: `scontrol show job <jobid>` gives the resolved
  request including defaults Slurm filled in.
- For job arrays, the unit of scheduling is the task, not the array — size a task and
  check the array throttle (`%N` in `--array`).

Record the effective request as: nodes, tasks, CPUs/task, memory, GRES/GPUs, walltime,
partition, QoS, account.

## Step 2 — Establish what the work actually needs

Prefer measurement over inference. In descending order of trust:

1. **Prior runs of the same work** — the strongest evidence available.
   ```
   sacct -u $USER --starttime now-30days \
     --format=JobID,JobName%30,Partition,AllocCPUS,AllocTRES%40,ReqMem,MaxRSS,Elapsed,Timelimit,State,ExitCode
   seff <jobid>          # if installed: CPU efficiency, memory efficiency, walltime used
   ```
   Read `MaxRSS` against `ReqMem`, `Elapsed` against `Timelimit`, and CPU efficiency
   against `AllocCPUS`. `MaxRSS` is per-step high-water — check the `.batch`/step rows,
   not just the parent job row, or it reads as empty.

2. **A currently running instance** — `sstat -j <jobid>.batch --format=JobID,MaxRSS,AveCPU`.

3. **A deliberately small pilot** — when there is no history, recommend one short,
   cheap run to measure against instead of guessing. A pilot that waits 10 minutes beats
   a guess that wastes a 6-hour slot.

4. **Structural reasoning** — only when nothing above is available, and label it as an
   estimate: model parameters × bytes/param × optimizer-state multiplier for VRAM, dataset
   size for host memory, dataloader workers for CPUs.

If none of these produce evidence, say so plainly. **Do not shrink an allocation on a
guess** — report that the request is unverifiable and recommend a pilot.

Then identify the **binding dimension**: the single resource that actually gates the job.
Everything else is either free or follows from it (e.g. CPUs and memory are usually
implied by the GPU count on a shared node).

## Step 3 — Price the queue

```
squeue -u $USER --start                     # backfill estimate for your pending jobs
sbatch --test-only <script>                 # validate + estimated start, submits nothing
squeue -p <partition> --noheader | wc -l    # queue depth
sinfo -p <partition> -o "%P %a %l %D %t %C %G"   # limits, node states, CPU alloc/idle/other/total
scontrol show partition <partition>         # MaxTime, DefaultTime, per-partition limits
sprio -j <jobid> -l ; sshare -U             # why this job ranks where it does
```

For an already-pending job, `squeue -j <jobid> -o "%r"` gives the pending reason.
`Priority` means it is queued behind others; `Resources` means it is next but the hardware
is not free; `PartitionTimeLimit`, `QOSMax*`, `AssocMax*` mean the request is illegal or
capped and will *never* start as written — those are correctness bugs, not wait problems.

**Treat estimated start times as weak signals.** Slurm's backfill estimate is a projection
that assumes every running job uses its full walltime, and it is revised continuously. A
study of ARCHER2 and Cirrus (arXiv:2204.13543) found initial predictions landed within a
minute of the true start for only ~5% and ~0.4% of jobs respectively. Use `--start` to compare *options*
(does halving the GPU count move the estimate from tomorrow to this afternoon?), never to
promise the user a start time.

## Step 4 — Decide

Recommend a reduction only when **both** hold:

- **Oversized on the binding dimension** — measured usage plus headroom is well under the
  request. Rough thresholds: memory high-water below ~60% of `--mem`, CPU efficiency below
  ~50%, elapsed below ~50% of `--time`, or GPUs allocated beyond what the parallelism
  strategy uses.
- **The reduction crosses a scheduling boundary** — it changes the set of nodes or the
  time windows the job can land in. Boundaries that matter: whole-node vs. shared
  thresholds, GPUs-per-node counts (asking for 5 GPUs on 4-GPU nodes forces 2 nodes),
  node count, a partition or QoS walltime tier, per-user TRES caps, and the backfill
  window ahead of a large reserved job.

If it is oversized but the wait is already short, say so and leave it alone — churn has
its own cost. If the wait is long but the request is honest, say that too; the answer is
patience or a different partition, not a smaller job.

**Walltime is usually the highest-leverage knob.** Requesting the partition maximum "to be
safe" is the single most common cause of long waits: it makes the job invisible to the
backfill scheduler, which can only start a job it can prove will finish before the
reserved large job begins. A walltime set from `Elapsed` history plus margin often moves a
job forward more than cutting hardware does.

### Guardrails

- **Propose, do not silently shrink.** Present the change and the reasoning; let the user
  approve it.
- **Never trim below observed high-water plus margin.** Suggested floors: memory at
  ~1.3× `MaxRSS`, walltime at ~1.5× median `Elapsed` (more if runtime is variable or the
  job is not checkpointed). Under-requesting is not free — an OOM or a `TIMEOUT` at hour
  11 costs the full wait again plus the burned compute.
- **Check the reduction is still legal** — it must satisfy partition, QoS, and association
  limits, and stay above any minimum node/CPU count the partition enforces.
- **Preemptible and requeue-on-fail partitions change the math.** A cheap fast start on a
  preemptible queue is only a win if the work checkpoints.
- **Never run `sbatch`, `scancel`, or `scontrol requeue` without explicit confirmation.**
  `sbatch --test-only` and every read-only query above are safe to run unprompted.

## Report format

Keep it to a table plus a recommendation:

| Dimension | Requested | Evidence of need | Recommend |
|---|---|---|---|
| GPUs | 4 | prior run used 1 (no tensor parallelism in config) | **1** |
| Memory | 256G | MaxRSS 41G across 3 runs | **64G** |
| Walltime | 48h (partition max) | median Elapsed 3h12m, max 3h40m | **6h** |
| CPUs | 32 | seff CPU efficiency 18% | 8 |

Then state, in two or three sentences: the binding dimension, which scheduling boundary
the reduction crosses, the observed effect on the estimated start (with the caveat that it
is an estimate), and the risk if the smaller request turns out to be wrong.

## Site customization

This skill is deliberately cluster-agnostic. If you work on one cluster regularly, add a
sibling `references/<cluster>.md` with its real partitions, walltime tiers, GPU type
strings, per-user caps, and node inventory, and reference it here — measured site facts
beat discovery commands every time, and they remove the guessing this skill otherwise has
to warn about.
