# ParRes Kernels WASM Build and Run

Build is working fine. Running locally most of the functions work all right.
To run, from within the client container run:
```
inv upload.user prk
kernels_pool_runner <func_name: dgemm, global, nstream, ..> <np>
```

## DGEMM
+ Missing import `env.{MPI_Comm_group,MPI_Group_incl,MPI_Comm_create}`

## Global
+ Core dumped: out of boudnds at some point

## Nstream
+ Ran ok!

## p2p
+ Ran ok!

## Random
+ `MPI_Alltoallv` not implemented

## Reduce
+ Ran ok!

## Sparse
+ Ran ok! (Need to have `pow(2, arg[1]) % np == 0`)

## Stencil
+ Ran ok!

## Transpose
+ Ran ok!

# Problems
1. Can't run via `invoke`: `RPC error function share`
