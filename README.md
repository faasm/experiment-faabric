# Faabric Experiments

This repo contains the experiments for the [Faabric paper](
https://arxiv.org/abs/2302.11358).

This repo should be checked out as part of the Faasm experiment set-up covered
in the [`experiment-base` repo](https://github.com/faasm/experiment-base).

To check things are working:

```bash
source ../../bin/workon.sh

inv -l
```

## Experiment status

| Experiment Name | Native | Granny | Plots |
|---|---|---|---|
| Array:MPI:Saturated |  |  | |
| Array:MPI:Unsaturated |  |  | |
| Array:OMP:Saturated |  |  | |
| Array:OMP:Unsaturated |  |  | |
| Other:Scale |  |  | |
| [Benefits:MPI:Consolidation](./tasks/migration) |  |  | |
| Benefits:OMP:Elasticity |  |  | |
| FT:Granule |  |  | |
| FT:Node |  |  | |
| FT:Deployment |  |  | |

EM Experiments (in order of priority):
1. Array:MPI:Saturated
2. Array:OMP:Saturated
3. Array:MPI:Unsaturated
4. Array:OMP:Unsaturated
5. Other:Scale

CS Experiments (in order of priority):
1. Benefits:MPI:Consolidation
2. Benefits:OMP:Elasticity
3. FT:Granule
4. FT:Node
5. FT:Deployment
