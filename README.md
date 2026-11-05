# Clima

Empty Python project scaffold for data analysis and machine learning.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The project includes NumPy, pandas, seaborn, scikit-learn, and SciPy. Statistical
utilities are available through `scipy.stats`.



Dati: 

https://github.com/owid/co2-data/

1. Per la Temperatura Globale 🌍
Our World in Data offre già i dati storici elaborati in formato tabellare. Puoi scaricare la tabella delle anomalie termiche annuali direttamente da:
• Our World in Data - Annual Temperature Anomalies: mostra lo scostamento termico globale annuale rispetto alla media storica.
• In alternativa, il dataset scientifico di riferimento più utilizzato è il NASA GISS Surface Temperature Analysis (GISTEMP), che fornisce file CSV pronti con le temperature medie globali dal 1880 a oggi: https://data.giss.nasa.gov/gistemp/ e https://data.giss.nasa.gov/gistemp/data_v4.html 

Nota (global temp e baseline)

Data set: Global-mean monthly, seasonal, and annual means, 1880-present, updated through most recent month: TXT, CSV

La baseline ufficiale utilizzata dalla NASA per il dataset GISTEMP v4 è il periodo di 30 anni che va dal 1951 al 1980.
Ecco come funziona il calcolo:
1. La NASA ha calcolato la temperatura media assoluta del pianeta per ciascun mese del trentennio 1951-1980.
2. Quella media trentennale è stata fissata come il punto 0 °C (il valore di riferimento).
3. Tutti gli altri anni vengono espressi come "scostamento" da quel valore dello zero.




2. Per l'Irradiazione Solare (Total Solar Irradiance - TSI) ☀️L'irradiazione solare non è presente nei cataloghi standard sulle emissioni di OWID. La tabella standard globale utilizzata dalla comunità scientifica per studiare le correlazioni climatiche è: Predecessore e prosecuzione del dataset IPCC / NOAA TSI: Il dataset storico sulla Total Solar Irradiance (ricostruzione LISIRD/LASP della NASA o i dati NOAA) fornisce l'energia solare espressa in \(W/m^2\) su base annua dal 1610 a oggi.


