import pandas as pd
import numpy as np

url = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
df = pd.read_csv(url)

dataset = df

# 1. Ordina il dataset per paese e per anno (fondamentale per le serie storiche)
dataset = dataset.sort_values(by=['country', 'year']).reset_index(drop=True)


# 2. Funzione generica di pulizia esponenziale a prova di nulli iniziali
def pulisci_esponenziale_gruppo(group):
    # Trasforma in logaritmo (gestendo gli zeri)
    log_serie = np.log(group.replace(0, np.nan))
    
    # Interpola i valori intermedi
    log_serie = log_serie.interpolate(method='linear')
    
    # RISOLUZIONE PRIMO VALORE NULLO: bfill copia all'indietro il primo valore valido
    log_serie = log_serie.ffill().bfill()
    
    # Riconverti alla scala originale
    return np.exp(log_serie)

# 3. Applica l'algoritmo separatamente per ogni paese su entrambe le colonne
dataset['population'] = dataset.groupby('country')['population'].transform(pulisci_esponenziale_gruppo)
dataset['gdp'] = dataset.groupby('country')['gdp'].transform(pulisci_esponenziale_gruppo)

# 4. Sicurezza finale per paesi totalmente privi di dati storici
dataset['population'] = dataset['population'].fillna(0)
dataset['gdp'] = dataset['gdp'].fillna(0)

dataset