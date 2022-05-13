#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

int doAlltoAll(int rank, int worldSize, int i)
{
    int retVal = 0;
    int chunkSize = 2;
    int fullSize = worldSize * chunkSize;

    // Arrays for sending and receiving
    int* sendBuf = new int[fullSize];
    int* expected = new int[fullSize];
    int* actual = new int[fullSize];

    // Populate data
    for (int i = 0; i < fullSize; i++) {
        // Send buffer from this rank
        sendBuf[i] = (rank * 10) + i;

        // Work out which rank this chunk of the expectation will come from
        int rankOffset = (rank * chunkSize) + (i % chunkSize);
        int recvRank = i / chunkSize;
        expected[i] = (recvRank * 10) + rankOffset;
    }

    MPI_Alltoall(
      sendBuf, chunkSize, MPI_INT, actual, chunkSize, MPI_INT, MPI_COMM_WORLD);

    delete[] sendBuf;
    delete[] actual;
    delete[] expected;

    return retVal;
}

// Outer wrapper, and re-entry point after migration
void doBenchmark(int nLoops)
{
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

        doAlltoAll(rank, worldSize, i);
    }

    printf("Rank %i exitting the loop\n", rank);
    MPI_Barrier(MPI_COMM_WORLD);

    // Shutdown
    MPI_Finalize();
}

int main(int argc, char* argv[])
{
    if (argc != 2) {
        printf("Must provide one input argument: <NUM_LOOPS>\n");
        return 1;
    }

    // Filthy hack to set the check period without modifying the function
    // signature. Note that the migrated functions won't see the updated
    // value as we don't migrate global variables, but that's OK as we don't
    // support migrating a function twice.
    int numLoops = atoi(argv[1]);

    printf(
      "Starting MPI migration with %i loops!\n", numLoops);

    doBenchmark(numLoops);

    printf("MPI migration benchmark finished succesfully\n");
}
