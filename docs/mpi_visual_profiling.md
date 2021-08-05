# Profiling MPI (more or less)

## TL-DR

**What works good? (in order of importance imo):**
  + Few MPI calls
  + A lot of in-iteration logic.
  + `MPI_Allgather` and `MPI_Reduce`

**What works bad?:**
  + A lot of different granular MPI calls.
  + From the benchmarks, point to point synch and async primitives.

## Results interpretation

A quick look over just the MPI calls, seems to indicate that the main
performance bottleneck is in point-to-point communication, whereas collective
communication principles like broadcast and reduce seem not to be too bad.

This is, however, contradictory with the implementation, as we do no smart thing
with collective communication principles, just a bunch of sends and receives.

A closer look, examining the source code, corroborates these observations.
In particular, the experiments that behave the best only test few MPI primitives
like `MPI_Allgather` and `MPI_Reduce`.
The experiments that behave the worst perform more MPI calls and specially
point-to-point communications.

## MPI Usage Static Analysis Results

### Sparse

Performance: OK

Description: sparse matrix multiplication.

Strongly used: `MPI_Allgather`

```bash
  "MPI_BCAST": 6,
  "MPI_ALLGATHER": 1,
  "MPI_REDUCE": 2,
```

### Nstream

Performance: OK

Description: 

Strongly used: nothing? but `MPI_Barrier`

```bash
  "MPI_BCAST": 3,
  "MPI_REDUCE": 1,
```

### Reduce

Performance: +o-

Description: literally test the performance of reduce.

Strongly used: `MPI_Reduce`

```bash
  "MPI_BCAST": 2,
  "MPI_REDUCE": 3,
```

### Stencil

Performance: bad

Description: apply a stencil (linear filter) to a grid/image.

Strongly used: `MPI_Irecv` and `MPI_Isend`.

```bash
  "MPI_REDUCE": 2,
  "MPI_BCAST": 2,
  "MPI_WAIT": 8,
  "X_MPI_DTYPE": 2,
  "MPI_IRECV": 4,
  "MPI_ISEND": 4,
```

### p2p

Performance: bad

Description: test the efficiency of point-to-point communication.

Strongly used: `MPI_Recv` and `MPI_Send`.

```bash
  "MPI_BCAST": 4,
  "MPI_RECV": 3,
  "MPI_SEND": 3,
  "MPI_REDUCE": 1,
```

### Transpose

Performance: +o-

Description: test the efficiency of transposing a large matrix.

Strongly used: `MPI_Recv`, `MPI_Isend`, and `MPI_Sendrecv` but with way more 
complexity per iteration.

```bash
  "MPI_REDUCE": 2,
  "MPI_BCAST": 3,
  "MPI_SENDRECV": 1,
  "MPI_WAIT": 2,
  "MPI_IRECV": 1,
  "MPI_ISEND": 1,
```
