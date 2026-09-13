#!/usr/bin/env python3
"""
superposition.py
=================

The Superposition and Coin Analogy: Phase and Interference on Real
Quantum Hardware.

This script builds physical intuition for qubit superposition, measurement
basis, quantum phase, and interference by comparing a single qubit to a
classical coin -- then systematically testing where that analogy breaks
down using experiments executed on real IBM Quantum hardware via Qiskit.

Experiments performed (in order):
    1. Classical coin flip (baseline, no quantum hardware).
    2. Quantum coin (Hadamard gate) measured in the Z basis.
    3. Quantum coin measured in the X basis (basis-dependence).
    4. Double Hadamard gate -- interference restores the original state.
    5. Hadamard-Phase(pi)-Hadamard -- phase flips the interference outcome.
    6. sqrt(NOT) (SX) gate measured along X, Y, Z (the "coin on its edge").
    7. Bloch sphere visualization of NOT, sqrt(NOT), PHASE, and Hadamard.

Requirements:
    qiskit>=2.1.0, qiskit-ibm-runtime>=0.40.1, qiskit-aer>=0.17.0,
    numpy, pylatexenc, matplotlib

Usage:
    export QISKIT_IBM_TOKEN="your_ibm_quantum_api_token"
    python superposition.py --shots 1000 --output-dir results

Author:
    Muhammad Danyal
"""

from __future__ import annotations

import argparse
import logging
import os
import random
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # Render to files; no GUI backend required.
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import Pauli  # noqa: E402
from qiskit.transpiler.preset_passmanagers import (  # noqa: E402
    generate_preset_pass_manager,
)
from qiskit.visualization import (  # noqa: E402
    plot_bloch_multivector,
    plot_histogram,
)
from qiskit_ibm_runtime import (  # noqa: E402
    EstimatorV2 as Estimator,
    QiskitRuntimeService,
    SamplerV2 as Sampler,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("superposition")

DEFAULT_SHOTS = 1000


# --------------------------------------------------------------------------- #
# Setup helpers
# --------------------------------------------------------------------------- #

def get_runtime_service() -> QiskitRuntimeService:
    """Load an authenticated IBM Quantum Runtime service.

    The API token is read from the ``QISKIT_IBM_TOKEN`` environment
    variable (or from previously saved account credentials) -- it is
    never hard-coded in source.

    Returns:
        A ready-to-use ``QiskitRuntimeService`` instance.

    Raises:
        RuntimeError: If no token is available and no account has
            already been saved locally.
    """
    token = os.environ.get("QISKIT_IBM_TOKEN")
    if token:
        QiskitRuntimeService.save_account(
            channel="ibm_quantum_platform",
            token=token,
            overwrite=True,
            set_as_default=True,
        )
        logger.info("Saved IBM Quantum account credentials from environment.")

    try:
        return QiskitRuntimeService(channel="ibm_quantum_platform")
    except Exception as exc:  # pragma: no cover - depends on live account
        raise RuntimeError(
            "Could not load IBM Quantum Runtime credentials. Set the "
            "QISKIT_IBM_TOKEN environment variable, or save an account "
            "with QiskitRuntimeService.save_account(...) beforehand."
        ) from exc


def get_least_busy_backend(service: QiskitRuntimeService):
    """Return the least-busy operational real (non-simulator) backend."""
    backend = service.least_busy(operational=True, simulator=False)
    logger.info("Using backend: %s (%d qubits)", backend.name, backend.num_qubits)
    return backend


def transpile_for_backend(circuit: QuantumCircuit, backend) -> QuantumCircuit:
    """Transpile a circuit to the backend's ISA at optimization level 3."""
    pass_manager = generate_preset_pass_manager(
        target=backend.target, optimization_level=3
    )
    return pass_manager.run(circuit)


def save_figure(fig, output_dir: Path, name: str) -> Path:
    """Save a Matplotlib figure to ``output_dir/name.png`` and close it."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figure: %s", path)
    return path


# --------------------------------------------------------------------------- #
# Part 1: Classical coin vs. quantum coin
# --------------------------------------------------------------------------- #

def classical_coin_flip(shots: int, output_dir: Path) -> list[int]:
    """Simulate ``shots`` classical coin flips and plot the histogram.

    Args:
        shots: Number of coin flips to simulate.
        output_dir: Directory to save the resulting histogram image.

    Returns:
        The list of simulated flip outcomes (0 or 1).
    """
    flips = [random.randint(0, 1) for _ in range(shots)]
    fig, ax = plt.subplots()
    ax.hist(flips, bins=2)
    ax.set_title("Classical Coin Flip (n=%d)" % shots)
    save_figure(fig, output_dir, "classical_coin_histogram")
    return flips


def build_quantum_coin_circuit() -> QuantumCircuit:
    """Build the quantum-coin circuit: Hadamard gate followed by measurement."""
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.measure_all()
    return circuit


# --------------------------------------------------------------------------- #
# Part 2: Quantum coin on real hardware (Z basis)
# --------------------------------------------------------------------------- #

def run_quantum_coin_z_basis(backend, shots: int, output_dir: Path) -> dict:
    """Run the Hadamard quantum-coin circuit on hardware, Z basis (Sampler)."""
    circuit = build_quantum_coin_circuit()

    fig = circuit.draw("mpl")
    save_figure(fig, output_dir, "quantum_coin_circuit")

    isa_circuit = transpile_for_backend(circuit, backend)
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    counts = job.result()[0].data.meas.get_counts()

    fig = plot_histogram(counts)
    save_figure(fig, output_dir, "quantum_coin_hardware_histogram")
    logger.info("Quantum coin (Z basis) counts: %s", counts)
    return counts


# --------------------------------------------------------------------------- #
# Part 3: Superposition in three dimensions (X basis)
# --------------------------------------------------------------------------- #

def run_quantum_coin_x_basis(backend) -> float:
    """Measure the expectation value of X for H|0>, revealing basis-dependence."""
    circuit = QuantumCircuit(1)
    circuit.h(0)
    observable = Pauli("X")

    isa_circuit = transpile_for_backend(circuit, backend)
    isa_observable = observable.apply_layout(layout=isa_circuit.layout)

    estimator = Estimator(mode=backend)
    job = estimator.run([(isa_circuit, isa_observable)])
    expectation_value = float(job.result()[0].data.evs)
    logger.info("Quantum coin <X> expectation value: %.3f", expectation_value)
    return expectation_value


# --------------------------------------------------------------------------- #
# Part 4: Quantum phase and interference
# --------------------------------------------------------------------------- #

def run_double_hadamard(backend, shots: int, output_dir: Path) -> dict:
    """Apply H twice; interference should deterministically restore |0>."""
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.h(0)
    circuit.measure_all()

    fig = circuit.draw("mpl")
    save_figure(fig, output_dir, "double_hadamard_circuit")

    isa_circuit = transpile_for_backend(circuit, backend)
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    counts = job.result()[0].data.meas.get_counts()

    fig = plot_histogram(counts)
    save_figure(fig, output_dir, "double_hadamard_histogram")
    logger.info("Double Hadamard counts: %s", counts)
    return counts


def run_phase_interference(backend, shots: int, output_dir: Path) -> dict:
    """Apply H, PHASE(pi), H; the inserted phase flips the outcome to |1>."""
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.p(np.pi, 0)
    circuit.h(0)
    circuit.measure_all()

    fig = circuit.draw("mpl")
    save_figure(fig, output_dir, "phase_gate_circuit")

    isa_circuit = transpile_for_backend(circuit, backend)
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    counts = job.result()[0].data.meas.get_counts()

    fig = plot_histogram(counts)
    save_figure(fig, output_dir, "phase_gate_histogram")
    logger.info("Hadamard-Phase(pi)-Hadamard counts: %s", counts)
    return counts


# --------------------------------------------------------------------------- #
# Part 5: sqrt(NOT) gate -- "coin on its edge"
# --------------------------------------------------------------------------- #

def run_sqrt_not_three_axes(backend, output_dir: Path) -> Sequence[float]:
    """Measure <X>, <Y>, <Z> for the sqrt(NOT) (SX) gate applied to |0>."""
    circuit = QuantumCircuit(1)
    circuit.sx(0)

    fig = circuit.draw("mpl")
    save_figure(fig, output_dir, "sqrt_not_circuit")

    observables = [Pauli("X"), Pauli("Y"), Pauli("Z")]
    isa_circuit = transpile_for_backend(circuit, backend)
    isa_observables = [obs.apply_layout(layout=isa_circuit.layout) for obs in observables]

    estimator = Estimator(mode=backend)
    job = estimator.run([(isa_circuit, isa_observables)])
    expectation_values = job.result()[0].data.evs
    logger.info(
        "sqrt(NOT) expectation values -- X: %.3f, Y: %.3f, Z: %.3f",
        *expectation_values,
    )
    return expectation_values


# --------------------------------------------------------------------------- #
# Part 6: Bloch sphere visualization of each gate
# --------------------------------------------------------------------------- #

def plot_gate_bloch_spheres(output_dir: Path) -> None:
    """Visualize NOT, sqrt(NOT), PHASE(pi), and Hadamard on the Bloch sphere.

    These are statevector visualizations (no hardware execution required)
    that show every single-qubit gate as a deterministic rotation.
    """
    gates = {
        "bloch_not_gate": lambda qc: qc.x(0),
        "bloch_sqrt_not_gate": lambda qc: qc.sx(0),
        "bloch_phase_gate": lambda qc: qc.p(np.pi, 0),
        "bloch_hadamard_gate": lambda qc: qc.h(0),
    }
    for name, apply_gate in gates.items():
        circuit = QuantumCircuit(1)
        apply_gate(circuit)
        fig = plot_bloch_multivector(circuit)
        save_figure(fig, output_dir, name)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the superposition/coin-analogy experiments on real IBM "
            "Quantum hardware and save all resulting figures."
        )
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=DEFAULT_SHOTS,
        help="Number of shots for each sampled circuit (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("images"),
        help="Directory to save all generated figures (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    """Run every experiment in sequence and save all resulting figures."""
    args = parse_args()

    logger.info("Part 1: Classical coin flip baseline (%d flips).", args.shots)
    classical_coin_flip(args.shots, args.output_dir)

    logger.info("Connecting to IBM Quantum Runtime and selecting a backend...")
    service = get_runtime_service()
    backend = get_least_busy_backend(service)

    logger.info("Part 2: Quantum coin on real hardware (Z basis).")
    run_quantum_coin_z_basis(backend, args.shots, args.output_dir)

    logger.info("Part 3: Quantum coin measured in the X basis.")
    run_quantum_coin_x_basis(backend)

    logger.info("Part 4a: Double Hadamard interference.")
    run_double_hadamard(backend, args.shots, args.output_dir)

    logger.info("Part 4b: Hadamard-Phase(pi)-Hadamard interference.")
    run_phase_interference(backend, args.shots, args.output_dir)

    logger.info("Part 5: sqrt(NOT) gate measured along X, Y, Z.")
    run_sqrt_not_three_axes(backend, args.output_dir)

    logger.info("Part 6: Bloch sphere visualization of all gates.")
    plot_gate_bloch_spheres(args.output_dir)

    logger.info("All experiments complete. Figures saved to: %s", args.output_dir)


if __name__ == "__main__":
    main()
