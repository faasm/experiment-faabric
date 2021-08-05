import os

KERNELS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname((os.path.realpath(__file__))))
)
BASE_DIR = "{}/../experiment-base".format(KERNELS_DIR)
RESULT_FILE_FAASM = "{}/results/kernels/kernels_faasm_aks.dat".format(BASE_DIR)
RESULT_FILE_NATIVE = "{}/results/kernels/kernels_native_aks.dat".format(BASE_DIR)
