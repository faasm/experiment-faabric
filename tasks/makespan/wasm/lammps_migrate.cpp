#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

#include <faasm/faasm.h>
#include <faasm/migrate.h>

int numLoops;

int doLammpsSimulation()
{
    // Chain to lammps/main (note that this function must also belong to user
    // lammps)
    int callId = faasmChainNamed("main");
    int result = faasmAwaitCall(callId);
    return result;
}

void doBenchmark(int nLoops)
{
    bool mustCheck = nLoops == NUM_LOOPS;

    // Initialisation
    int res = MPI_Init(NULL, NULL);
    if (res != MPI_SUCCESS) {
        printf("Failed on MPI init\n");
        return;
    }

    int rank;
    int worldSize;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &worldSize);

    for (int i = 0; i < nLoops; i++) {
        if (rank == 0 && i % (nLoops / 10) == 0) {
            printf("Starting iteration %i/%i\n", i, nLoops);
        }

        // Make sure everyone is in sync (including those ranks that have been
        // migrated)
        MPI_Barrier(MPI_COMM_WORLD);

        int result = doLammpsSimulation();

        // Migration point, which may or may not resume the
        // benchmark on another host for the remaining iterations.
        // This would eventually be MPI_Barrier
        MPI_Barrier(MPI_COMM_WORLD);
        __faasm_migrate_point(&doBenchmark, (nLoops - i - 1));
    }
}

/* Run a number of LAMMPS simulations, one after the other, and check for migration
 * opportunities between each one.
 */
int main(int argc, char** argv)
{
    if (argc != 2) {
        printf("Must provide one input argument: <check_period>\n");
        return 1;
    }

    // Filthy hack to set the check period without modifying the function
    // signature. Note that the migrated functions won't see the updated
    // value as we don't migrate global variables, but that's OK as we don't
    // support migrating a function twice.
    int numLoopsIn = atoi(argv[1]);
    int* numLoopsPtr = &numLoops;
    *numLoopsPtr = numLoopsIn;

    printf("Running %i chained LAMMPS simulations\n", *numLoopsPtr);

    doBenchmark(*numLoopsPtr);

    printf("MPI chained simulation benchmark finished succesfully\n");
}
