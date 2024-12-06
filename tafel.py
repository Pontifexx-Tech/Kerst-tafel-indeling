import pandas as pd
import random
from collections import defaultdict

# Definieer de tafelgroottes
TABLE_SIZES = {
    1: 10, 2: 10, 3: 10, 4: 10,  # Tafels met 10 personen
    5: 8, 6: 8, 7: 8, 8: 8, 9: 8, 10: 8  # Tafels met 8 personen
}


def load_data_from_csv(filename):
    """Laad data uit CSV bestand met verschillende encoding opties"""
    try:
        # Probeer eerst met UTF-8
        df = pd.read_csv(filename, sep=';', encoding='utf-8')
    except UnicodeDecodeError:
        try:
            # Probeer dan met Windows encoding
            df = pd.read_csv(filename, sep=';', encoding='cp1252')
        except UnicodeDecodeError:
            # Als laatste optie, probeer Latin-1
            df = pd.read_csv(filename, sep=';', encoding='latin-1')

    df.set_index('Persoon', inplace=True)
    return df


def has_met_mc(person, mc, assignments, current_round_assignments):
    """Check of een persoon al een keer bij hun MC heeft gezeten"""
    if pd.isna(mc):  # Als persoon geen MC heeft
        return True

    for round_assignments in assignments.values():
        # Check huidige ronde
        if person in current_round_assignments and mc in current_round_assignments:
            if current_round_assignments[person] == current_round_assignments[mc]:
                return True

        # Check eerdere rondes
        if person in round_assignments and mc in round_assignments:
            if round_assignments[person] == round_assignments[mc]:
                return True
    return False


def get_table_current_size(table, assignments, df):
    """Bereken huidige tafelgrootte rekening houdend met huishoudgrootte"""
    current_size = 0
    for person, assigned_table in assignments.items():
        if assigned_table == table:
            current_size += df.loc[person, 'aantal']
    return current_size


def check_constraints(person, table, round_num, assignments, df, current_round_assignments):
    """Controleert of een persoon aan een bepaalde tafel kan worden toegewezen"""

    # Check tafelgrootte met huishouden
    household_size = df.loc[person, 'aantal']
    current_table_size = get_table_current_size(table, current_round_assignments, df)
    if current_table_size + household_size > TABLE_SIZES[table]:
        return False

    # Check of persoon niet al eerder bij dezelfde mensen heeft gezeten
    current_table_occupants = {p for p, t in current_round_assignments.items() if t == table}

    for other_round in [1, 2, 3]:
        if other_round == round_num:
            continue

        if other_round in assignments:
            previous_table = assignments[other_round].get(person)
            if previous_table is not None:
                previous_tablemates = {p for p, t in assignments[other_round].items() if t == previous_table}
                if any(p in current_table_occupants for p in previous_tablemates):
                    return False

    return True


def calculate_table_score(person, table, round_num, assignments, df, current_round_assignments):
    """Bereken een score voor een tafel, rekening houdend met MC-voorwaarde"""
    score = 0

    # Als persoon een MC heeft en nog niet bij MC heeft gezeten
    if 'MC' in df.columns and not pd.isna(df.loc[person, 'MC']):
        mc = int(df.loc[person, 'MC'])
        if not has_met_mc(person, mc, assignments, current_round_assignments):
            # Check of MC aan deze tafel zit
            if mc in current_round_assignments and current_round_assignments[mc] == table:
                score += 1000  # Hoge score voor MC-match

    return score


def assign_tables(df, round_num, existing_assignments):
    """Wijst tafels toe voor een bepaalde ronde"""
    assignments = {}
    unassigned = set(df.index)

    # Verwijder mensen die al zijn ingedeeld
    for person in df.index:
        if pd.notna(df.loc[person, f'Ronde {round_num}']):
            assignments[person] = int(df.loc[person, f'Ronde {round_num}'])
            unassigned.remove(person)

    # Sorteer ontoegewezen mensen op huishoudgrootte (grootste eerst)
    unassigned = sorted(list(unassigned),
                        key=lambda x: df.loc[x, 'aantal'],
                        reverse=True)

    # Probeer mensen in te delen
    for person in unassigned:
        valid_tables = []
        table_scores = []

        for table in range(1, 11):
            if check_constraints(person, table, round_num, existing_assignments, df, assignments):
                valid_tables.append(table)
                score = calculate_table_score(person, table, round_num, existing_assignments, df, assignments)
                table_scores.append((table, score))

        if valid_tables:
            # Kies tafel met hoogste score, of random als scores gelijk zijn
            table_scores.sort(key=lambda x: (x[1], random.random()), reverse=True)
            chosen_table = table_scores[0][0]
            assignments[person] = chosen_table
        else:
            # Als we vastlopen, begin opnieuw
            return None

    return assignments


def create_seating_plan(df):
    """Maakt een complete tafelindeling"""
    assignments = {3: {}}

    # Vul ronde 3 in vanuit de data
    for idx in df.index:
        if pd.notna(df.loc[idx, 'Ronde 3']):
            assignments[3][idx] = int(df.loc[idx, 'Ronde 3'])

    # Vul ronde 1 en 2 in
    for round_num in [1, 2]:
        max_attempts = 100
        attempt = 0
        round_assignments = None

        while round_assignments is None and attempt < max_attempts:
            round_assignments = assign_tables(df, round_num, assignments)
            attempt += 1

        if round_assignments is None:
            return None

        assignments[round_num] = round_assignments

    return assignments


def validate_table_sizes(df, solution):
    """Controleer of alle tafels niet over hun capaciteit gaan"""
    for round_num in [1, 2, 3]:
        if round_num in solution:
            table_sizes = defaultdict(int)
            for person, table in solution[round_num].items():
                table_sizes[table] += df.loc[person, 'aantal']

            for table, size in table_sizes.items():
                if size > TABLE_SIZES[table]:
                    print(
                        f"Waarschuwing: Tafel {table} in ronde {round_num} heeft {size} personen (max: {TABLE_SIZES[table]})")
                    return False
    return True


def validate_mc_meetings(df, solution):
    """Controleer of iedereen minimaal 1 keer bij hun MC heeft gezeten"""
    if 'MC' not in df.columns:
        return True

    for person in df.index:
        if pd.notna(df.loc[person, 'MC']):
            mc = int(df.loc[person, 'MC'])
            met_mc = False

            for round_num in solution:
                if person in solution[round_num] and mc in solution[round_num]:
                    if solution[round_num][person] == solution[round_num][mc]:
                        met_mc = True
                        break

            if not met_mc:
                print(f"Waarschuwing: Persoon {person} heeft niet bij MC {mc} gezeten")
                return False
    return True


def print_table_assignments(df, solution, round_num):
    """Print tafelindeling met aantal personen per tafel"""
    print(f"\nRonde {round_num}:")
    for table in range(1, 11):
        people_at_table = [p for p, t in solution[round_num].items() if t == table]
        total_people = sum(df.loc[p, 'aantal'] for p in people_at_table)
        print(f"Tafel {table} ({total_people}/{TABLE_SIZES[table]} personen):")
        for person in sorted(people_at_table):
            print(f"  - Persoon {person} ({df.loc[person, 'aantal']} personen)")


def save_results_to_csv(original_df, solution, output_filename):
    """Sla de resultaten op in een nieuw CSV bestand"""
    result_df = original_df.copy()

    for round_num in [1, 2]:
        if round_num in solution:
            for person, table in solution[round_num].items():
                result_df.loc[person, f'Ronde {round_num}'] = table

    result_df.to_csv(output_filename, sep=';')


# Hoofdprogramma
if __name__ == "__main__":
    input_filename = "kest202412.csv"  # Pas dit aan naar jouw bestandsnaam
    output_filename = "tafelindeling_resultaat.csv"

    print("CSV bestand laden...")
    df = load_data_from_csv(input_filename)

    print("Tafelindeling genereren...")
    for attempt in range(100):
        solution = create_seating_plan(df)
        if solution is not None and validate_table_sizes(df, solution) and validate_mc_meetings(df, solution):
            print(f"Oplossing gevonden na {attempt + 1} pogingen!")

            # Print gedetailleerde resultaten
            for round_num in [1, 2]:
                print_table_assignments(df, solution, round_num)

            # Sla de resultaten op
            save_results_to_csv(df, solution, output_filename)
            print(f"\nResultaten opgeslagen in {output_filename}")
            break
    else:
        print("Geen oplossing gevonden na 100 pogingen.")