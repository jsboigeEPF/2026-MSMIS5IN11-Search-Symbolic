"""
Tests du vérificateur : on part d'un planning valide, on le CASSE volontairement
de différentes façons, et on vérifie que chaque erreur est bien détectée.
Lancer :  python tests.py
"""
import copy

from fcfs import planifier_fcfs
from instance import generer_instance
from verificateur import planning_vers_seances, verifier


def test_verificateur():
    inst = generer_instance(graine=1, nb_semaines=4)
    pl = planifier_fcfs(inst)
    seances = planning_vers_seances(inst, pl)
    assert verifier(inst, seances)["valide"], "le planning FCFS devrait être valide"

    nv = inst.nouveaux_patients()
    p, q = nv[0], nv[1]

    def casse(modif, motif):
        s = copy.deepcopy(seances)
        modif(s)
        r = verifier(inst, s)
        assert not r["valide"] and any(motif in e for e in r["erreurs"]), (motif, r["erreurs"][:3])
        print(f"  OK  erreur détectée : {motif}")

    def seances_de(s, pid):
        return [x for x in s if x["patient"] == pid]

    # 1. une séance supprimée
    casse(lambda s: s.remove(seances_de(s, p.id)[-1]), "séances au lieu de")
    # 2. un trou dans la série (dernière séance décalée d'un jour)
    casse(lambda s: seances_de(s, p.id)[-1].__setitem__("jour", seances_de(s, p.id)[-1]["jour"] + 1),
          "non consécutives")
    # 3. changement de machine en cours de traitement
    def change_machine(s):
        x = seances_de(s, p.id)[-1]
        x["machine"] = (x["machine"] + 1) % len(inst.machines)
    casse(change_machine, "plusieurs machines")
    # 4. créneau horaire qui bouge
    def change_creneau(s):
        x = seances_de(s, p.id)[-1]
        x["creneau"] = (x["creneau"] + 3) % (inst.nb_creneaux - 1)
    casse(change_creneau, "créneau horaire non constant")
    # 5. machine incompatible (patient VMAT_complexe mis sur la machine 3D-only)
    pc = next(x for x in nv if x.technique == "VMAT_complexe")
    casse(lambda s: [x.__setitem__("machine", 0) for x in seances_de(s, pc.id)], "incompatible")
    # 6. début avant la fin de la préparation
    pp = next(x for x in nv if x.debut_au_plus_tot > 0)
    casse(lambda s: [x.__setitem__("jour", x["jour"] - x["jour"] - 1 + i)
                     for i, x in enumerate(sorted(seances_de(s, pp.id), key=lambda y: y["jour"]))],
          "au plus tôt")
    # 7. deux patients au même endroit au même moment
    def conflit(s):
        a = seances_de(s, q.id)[0]
        for x in seances_de(s, p.id):
            x["machine"], x["creneau"] = a["machine"], a["creneau"]
            x["jour"] = a["jour"] + (x["numero"] - 1)
    casse(conflit, "Conflit")
    # 8. patient oublié
    casse(lambda s: s.__init__([x for x in s if x["patient"] != p.id]), "non planifié")
    print("Tous les tests du vérificateur passent.")


if __name__ == "__main__":
    test_verificateur()
