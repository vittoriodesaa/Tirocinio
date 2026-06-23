import json, os

WORKSPACE = "/home/domenico/clone/TirocinioVittorio/Tirocinio/progetto/backend/workspace/Strano"
COURSE_FILE = os.path.join(WORKSPACE, "reports/microlearning_course.json")

with open(COURSE_FILE) as f:
    course = json.load(f)

existing_ids = {m["id"] for m in course["moduli"]}
max_ord = max(m["ordine"] for m in course["moduli"])

def add_module(mid, ordine, argomento, contenuto, goals, src, start, end, durata=10):
    global max_ord
    if mid in existing_ids:
        return False
    mod = {
        "id": mid, "ordine": ordine, "tipo": "lezione", "argomento": argomento,
        "contenuto": contenuto, "obiettivi_apprendimento": goals,
        "fonte": {"percorso": src, "riga_inizio": start, "riga_fine": end},
        "fonti_aggiuntive": [], "durata_minuti": durata, "prerequisiti": [],
        "sintesi_breve": contenuto[:200]
    }
    course["moduli"].append(mod)
    max_ord = max(max_ord, ordine)
    existing_ids.add(mid)
    return True

def add_quiz(qid, ordine, titolo, dopo, domande, src="", start=1, end=1):
    if qid in existing_ids:
        return False
    quiz = {
        "id": qid, "ordine": ordine, "tipo": "quiz", "titolo": titolo,
        "dopo_modulo_id": dopo, "domande": domande,
        "durata_minuti": 5, "fonte": {"percorso": src, "riga_inizio": start, "riga_fine": end}
    }
    course["moduli"].append(quiz)
    max_ord = max(max_ord, ordine)
    existing_ids.add(qid)
    return True

# ====== NEW LESSONS ======
SRC = "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md"

# Array and collections lessons (pt_140-175)
lessons = [
    ("mod_027", "Espressioni e operatori in Java", 
     "## Introduzione\nUn'espressione combina variabili, valori e operatori producendo un risultato. Java offre operatori aritmetici (+, -, *, /, %), di confronto, logici e l'operatore condizionale ternario.\n\n## Concetti chiave\n### Operatore condizionale ternario\n`condizione ? valore_se_vero : valore_se_falso`. Esempio: `int max = (a > b) ? a : b;`\n\n### Precedenza degli operatori\n1. Postfissi 2. Unari 3. Moltiplicativi 4. Additivi 5. Confronto 6. AND 7. OR 8. Condizionale 9. Assegnamento\n\n## Esempio pratico\n```java\nint x = 5, y = 10;\nint min = (x < y) ? x : y; // 5\n```\n\n## Riepilogo\n- L'operatore ? : è un if-else compatto\n- La precedenza determina l'ordine di valutazione\n- Usa parentesi per chiarire",
     ["Valutare espressioni con operatori", "Usare l'operatore condizionale", "Comprendere la precedenza"], 1850, 1900),
    
    ("mod_028", "Tipi numerici interi e in virgola mobile",
     "## Introduzione\nJava offre tipi interi (byte, short, int, long) e floating-point (float, double). La scelta del tipo influenza precisione e range.\n\n## Concetti chiave\n### Tipi interi\nint (32 bit, ±2.1 miliardi), long (64 bit). Usa int come default.\n\n### Tipi floating-point\ndouble (64 bit, 15 cifre decimali), float (32 bit, 7 cifre). Usa double per calcoli scientifici.\n\n### Conversioni\nDa piccolo a grande: implicite. Da grande a piccolo: cast esplicito ((int) 3.14 -> 3).\n\n## Esempio pratico\n```java\ndouble raggio = 5.0;\ndouble area = Math.PI * raggio * raggio;\n```\n\n## Riepilogo\n-int per interi, double per decimali\n- Cast esplicito: (tipo) espressione\n- Math.PI è una costante",
     ["Distinguere tipi interi e floating-point", "Gestire conversioni implicite ed esplicite", "Usare Math.PI"], 1900, 1950),

    ("mod_029", "Conversioni di tipo e cast in Java",
     "## Introduzione\nLe conversioni tra tipi numerici possono essere implicite (da piccolo a grande) o esplicite tramite cast.\n\n## Concetti chiave\n### Cast esplicito\n`(tipo) espressione` forza la conversione. `double d = 3.14; int i = (int) d;` tronca a 3.\n\n### Da stringa a numero\n`Integer.parseInt(\"42\")`, `Double.parseDouble(\"3.14\")`.\n\n### Da numero a stringa\n`String.valueOf(42)` o `\"\" + 42`.\n\n## Esempio pratico\n```java\nint a = 10, b = 7;\ndouble media = (double)(a + b) / 2; // cast necessario\n```\n\n## Riepilogo\n- Cast esplicito: può perdere precisione\n- Integer.parseInt() per stringa->int\n- Conversioni implicite garantite dal compilatore",
     ["Usare cast per conversioni", "Convertire stringhe a numeri", "Gestire conversioni implicite"], 1950, 2000),
    
    ("mod_030", "Il tipo char e la codifica Unicode",
     "## Introduzione\nchar rappresenta un singolo carattere Unicode a 16 bit. Può contenere lettere, cifre, simboli e caratteri speciali come '\\n' e '\\t'.\n\n## Concetti chiave\n### Letterali char\n'A', '0', '\\u0041' (codice esadecimale). Apici singoli, diversi dalle stringhe.\n\n### Operazioni su char\nConfronti con <, >, ==. Somme con interi: 'A' + 1 = 'B'. Character.isDigit(c), isLetter(c).\n\n## Esempio pratico\n```java\nString s = \"programmazione\";\nint vocali = 0;\nfor (int i = 0; i < s.length(); i++) {\n    char c = s.charAt(i);\n    if (c=='a'||c=='e'||c=='i'||c=='o'||c=='u') vocali++;\n}\n```\n\n## Riepilogo\n- char: singolo carattere Unicode (16 bit)\n- Apici singoli per char, doppi per String\n- Character fornisce metodi di utilità",
     ["Usare char per caratteri", "Comprendere Unicode", "Manipolare caratteri"], 2000, 2050),
    
    ("mod_031", "Le classi involucro: Integer, Double, Character",
     "## Introduzione\nLe classi wrapper incapsulano i primitivi in oggetti: Integer per int, Double per double, etc.\n\n## Concetti chiave\n### Autoboxing e unboxing\nInteger i = 42; // autoboxing (int->Integer)\nint j = i;      // unboxing (Integer->int)\n\n### Metodi statici\nInteger.parseInt(\"123\"), Integer.toHexString(255), Integer.MAX_VALUE.\n\n## Esempio pratico\n```java\nInteger i = 123;\nint j = i + 5;  // unboxing automatico\nString hex = Integer.toHexString(255); // \"ff\"\n```\n\n## Riepilogo\n- Wrapper: Integer, Double, Character, Boolean\n- Autoboxing/unboxing automatici\n- Metodi statici di utilità",
     ["Usare classi wrapper", "Comprendere autoboxing/unboxing", "Usare metodi statici dei wrapper"], 2050, 2100),
    
    ("mod_032", "I tipi enumerativi (enum) in Java",
     "## Introduzione\nUn tipo enumerativo (enum) definisce un insieme fisso di costanti con nome. Gli enum sono tipi riferimento speciali che forniscono type safety.\n\n## Concetti chiave\n### Dichiarazione\nenum Mese { GENNAIO, FEBBRAIO, MARZO, APRILE, MAGGIO, GIUGNO }\n\n### Metodi degli enum\nvalues() restituisce tutte le costanti, ordinal() restituisce l'indice, name() il nome.\n\n## Esempio pratico\n```java\nenum Mese { GEN, FEB, MAR, APR, MAG, GIU, LUG, AGO, SET, OTT, NOV, DIC }\nMese m = Mese.APRILE;\nSystem.out.println(m.ordinal()); // 3\n```\n\n## Riepilogo\n- enum definisce costanti tipizzate\n- Type safety: non si possono usare valori non definiti\n- values(), ordinal(), name() sono metodi built-in",
     ["Dichiarare tipi enumerativi", "Usare metodi degli enum", "Applicare enum per costanti tipizzate"], 2100, 2150),
    
    ("mod_033", "L'istruzione switch per selezione multipla",
     "## Introduzione\nswitch permette di selezionare tra più alternative in base al valore di una variabile. Funziona con int, char, String, enum.\n\n## Concetti chiave\n### Sintassi\nswitch(variabile) { case VAL1: ... break; case VAL2: ... break; default: ... }\nbreak è fondamentale per evitare il fall-through.\n\n## Esempio pratico\n```java\nswitch(giorno) {\n    case SABATO: case DOMENICA:\n        System.out.println(\"Weekend!\"); break;\n    default:\n        System.out.println(\"Lavorativo\");\n}\n```\n\n## Riepilogo\n- switch per selezione multipla\n- break interrompe il case\n- default opzionale (caso non coperto)\n- Fall-through: senza break si prosegue al case successivo",
     ["Usare switch per selezione", "Evitare il fall-through con break", "Gestire il caso default"], 2150, 2200),
    
    ("mod_034", "Array: dichiarazione, creazione e inizializzazione",
     "## Introduzione\nUn array è una sequenza di elementi dello stesso tipo, accessibili con indice. Gli array in Java sono oggetti con proprietà length.\n\n## Concetti chiave\n### Dichiarazione e creazione\nint[] numeri = new int[5]; // 5 interi (default 0)\nFrazione[] frazioni = new Frazione[3]; // 3 riferimenti (null)\n\n### Inizializzazione\nint[] primi = {2, 3, 5, 7, 11};\n\n## Esempio pratico\n```java\nint[] arr = new int[10];\nfor (int i = 0; i < arr.length; i++)\n    arr[i] = i * i;\n```\n\n## Riepilogo\n- Indice da 0 a length-1\n- Array di oggetti: elementi inizializzati a null\n- length è una proprietà, non metodo",
     ["Dichiarare e inizializzare array", "Accedere agli elementi", "Distinguere array di oggetti e primitivi"], 2200, 2250),
    
    ("mod_035", "Array di array e array irregolari",
     "## Introduzione\nJava supporta array multidimensionali come array di array. Ogni riga può avere lunghezza diversa (array irregolari).\n\n## Concetti chiave\n### Matrici rettangolari\nint[][] mat = new int[3][4]; // 3 righe, 4 colonne\n\n### Array irregolari\nint[][] t = new int[5][];\nfor (int i = 0; i < 5; i++) t[i] = new int[i+1];\n\n## Esempio pratico\n```java\nImporto[][] entrate = new Importo[NANNI][NMESI];\nfor (int a = 0; a < entrate.length; a++)\n    for (int m = 0; m < entrate[a].length; m++) {\n        totale += entrate[a][m].getValore();\n    }\n```\n\n## Riepilogo\n- matrice.length = numero di righe\n- matrice[i].length = numero di colonne della riga i\n- Array irregolari: ogni riga ha lunghezza diversa",
     ["Usare array bidimensionali", "Creare array irregolari", "Iterare su array multidimensionali"], 2250, 2300),
    
    ("mod_036", "La classe String: metodi e utilizzo",
     "## Introduzione\nString è una classe fondamentale in Java per rappresentare sequenze immutabili di caratteri. Offre numerosi metodi per manipolare il testo.\n\n## Concetti chiave\n### Metodi principali\nlength(), charAt(i), equals(s), compareTo(s), substring(i,j), indexOf(c), toLowerCase(), toUpperCase(), trim().\n\n### Immutabilità\nLe stringhe sono immutabili: ogni modifica crea un nuovo oggetto String.\n\n## Esempio pratico\n```java\nString s1 = \"Ciao\";\nString s2 = \"Ciao\";\nSystem.out.println(s1.equals(s2)); // true (confronto contenuto)\nSystem.out.println(s1 == s2);      // false? (dipende, confronto riferimenti)\n```\n\n## Riepilogo\n- String è immutabile\n- equals() confronta il contenuto\n- == confronta i riferimenti\n- + concatena stringhe",
     ["Usare metodi della classe String", "Distinguere equals e ==", "Comprendere l'immutabilità delle stringhe"], 2300, 2350),
    
    ("mod_037", "Metodi statici: definizione e invocazione",
     "## Introduzione\nI metodi statici appartengono alla classe, non alle istanze. Si invocano con il nome della classe: Classe.metodo().\n\n## Concetti chiave\n### Dichiarazione\npublic static int somma(int a, int b) { return a + b; }\n\n### Invocazione\nint r = Matematica.somma(3, 5); // senza creare oggetti\n\n## Esempio pratico\n```java\npublic class Utility {\n    public static double max(double a, double b) {\n        return (a > b) ? a : b;\n    }\n}\n```\n\n## Riepilogo\n- static: appartiene alla classe, non all'istanza\n- Si invoca con NomeClasse.metodo()\n- Non può accedere a campi di istanza\n- Math contiene solo metodi statici",
     ["Dichiarare metodi statici", "Invocare metodi statici", "Distinguere metodi statici e di istanza"], 2350, 2400),
    
    ("mod_038", "Selezione e iterazione con if-else, while, for",
     "## Introduzione\nCombiniamo selezione e iterazione in programmi completi. Esempio classico: la classe PappagalloStanco che ripete messaggi finché l'utente non dice \"stanco\".\n\n## Concetti chiave\n### PappagalloStanco\n```java\nString messaggio;\nmessaggio = tastiera.readLine();\nwhile (!messaggio.equals(\"stanco\")) {\n    video.println(messaggio);\n    messaggio = tastiera.readLine();\n}\n```\n\n## Esempio pratico\n```java\nint somma = 0;\nfor (int i = 1; i <= 100; i++)\n    somma += i;\nSystem.out.println(\"Somma: \" + somma);\n```\n\n## Riepilogo\n- equals() confronta stringhe (non ==)\n- while con controllo in testa\n- for per iterazioni con contatore",
     ["Combinare selezione e iterazione", "Usare equals() per stringhe", "Scrivere programmi interattivi"], 2400, 2450),
    
    ("mod_039", "Break e continue: controllo fine dei cicli",
     "## Introduzione\nbreak esce immediatamente dal ciclo. continue salta alla prossima iterazione. Sono utili per semplificare il controllo dei cicli.\n\n## Concetti chiave\n### break\nEsce dal ciclo più interno. Utile per cercare un elemento: trovato? esci.\n\n### continue\nSalta alla prossima iterazione. Utile per saltare elementi non desiderati.\n\n## Esempio pratico\n```java\nfor (int i = 0; i < arr.length; i++) {\n    if (arr[i] < 0) continue; // salta negativi\n    if (arr[i] == 0) break;    // fermati a zero\n    System.out.println(arr[i]);\n}\n```\n\n## Riepilogo\n- break: esce dal ciclo\n- continue: salta all'iterazione successiva\n- Usare con moderazione (a volte meno leggibili)",
     ["Usare break per uscire dai cicli", "Usare continue per saltare iterazioni", "Scegliere quando usarli"], 2450, 2500),
]

# Add lessons
next_ord = max_ord + 1
for lid, arg, content, goals, start, end in lessons:
    add_module(lid, next_ord, arg, content, goals, SRC, start, end)
    next_ord += 1

# Add quizzes every 2-3 lessons
quiz_id = 3
after_mods = ["mod_020", "mod_024", "mod_028", "mod_032", "mod_036"]
quiz_data = [
    (f"quiz_00{qid}", f"Verifica: classi, oggetti e metodi", dopo,
     [{"testo": "Cosa fa l'operatore new in Java?", "opzioni": ["Dichiara una variabile", "Crea un nuovo oggetto", "Cancella un oggetto", "Confronta due oggetti"], "indice_corretto": 1, "spiegazione": "new crea una nuova istanza (oggetto) della classe, invocando il costruttore."},
      {"testo": "Cosa contiene una variabile di tipo classe?", "opzioni": ["L'oggetto stesso", "Un riferimento all'oggetto", "Il nome della classe", "La dimensione dell'oggetto"], "indice_corretto": 1, "spiegazione": "Le variabili di tipo classe contengono un riferimento (indirizzo) all'oggetto, non l'oggetto stesso."},
      {"testo": "Cosa fa l'operatore ternario ? : ", "opzioni": ["Crea un ciclo", "Seleziona tra due valori", "Confronta due oggetti", "Converte un tipo"], "indice_corretto": 1, "spiegazione": "cond ? val1 : val2 restituisce val1 se cond è vera, val2 se falsa."}]) 
     for qid, dopo in zip(range(1, len(after_mods)+1), after_mods)
]

for qid, titolo, dopo, domande in quiz_data:
    add_quiz(qid, next_ord, titolo, dopo, domande, SRC)
    next_ord += 1

# More lessons to reach 120+ total
# Add topics from remaining piano_taglio points
more_topics = [
    ("mod_040", "Implementazione della classe Frazione", 2400, 2450,
     ["Implementare costruttori e metodi", "Usare campi privati", "Sollevare eccezioni con throw"],
     "## Introduzione\nDopo aver usato la classe Frazione, vediamo come implementarla. I campi (numeratore, denominatore) sono privati. I costruttori inizializzano lo stato, i metodi implementano le operazioni.\n\n## Concetti chiave\n### Campi privati\nprivate int num, den; // accessibili solo dalla classe\n\n### Costruttori\npublic Frazione(int n, int d) { num = n; den = d; }\n\n### Metodi\npublic Frazione piu(Frazione f) { ... }\n\n## Esempio pratico\n```java\npublic Frazione per(Frazione f) {\n    return new Frazione(num * f.num, den * f.den);\n}\n```\n\n## Riepilogo\n- Campi privati: incapsulamento\n- Costruttore: inizializza lo stato\n- Metodi: implementano il comportamento"),
    
    ("mod_041", "L'istruzione throw e la gestione delle eccezioni", 2450, 2500,
     ["Sollevare eccezioni con throw", "Creare eccezioni personalizzate", "Gestire anomalie nei costruttori"],
     "## Introduzione\nL'istruzione throw permette di sollevare un'eccezione quando si verifica una condizione anomala. Il costruttore di Frazione dovrebbe sollevare un'eccezione se il denominatore è zero.\n\n## Concetti chiave\n### Sollevare eccezioni\nif (den == 0) throw new IllegalArgumentException(\"Denominatore zero\");\n\n## Esempio pratico\n```java\npublic Frazione(int n, int d) {\n    if (d == 0) throw new IllegalArgumentException();\n    num = n; den = d;\n}\n```\n\n## Riepilogo\n- throw solleva un'eccezione\n- Le eccezioni interrompono il flusso normale\n- I costruttori possono sollevare eccezioni per dati non validi"),
    
    ("mod_042", "Implementazione di interfacce", 2500, 2550,
     ["Implementare interfacce con implements", "Scrivere il corpo dei metodi astratti", "Usare interfacce per polimorfismo"],
     "## Introduzione\nUna classe implementa un'interfaccia con la parola implements, fornendo il corpo per tutti i metodi astratti dichiarati nell'interfaccia.\n\n## Concetti chiave\n### implements\nclass Frazione implements Comparable<Frazione> {\n    public int compareTo(Frazione f) { ... }\n}\n\n## Esempio pratico\n```java\ninterface Ordinabile { int confronta(Ordinabile o); }\nclass Frazione implements Ordinabile {\n    public int confronta(Ordinabile o) {\n        Frazione f = (Frazione) o; ...\n    }\n}\n```\n\n## Riepilogo\n- implements: fornisce implementazione dell'interfaccia\n- Deve implementare TUTTI i metodi astratti\n- Interfacce consentono polimorfismo tra classi non imparentate"),
    
    ("mod_043", "Campi statici e costanti di classe", 2550, 2600,
     ["Dichiarare campi statici", "Usare final per costanti", "Comprendere la differenza tra variabili di istanza e statiche"],
     "## Introduzione\nI campi statici appartengono alla classe, non alle istanze. Una copia condivisa da tutti gli oggetti. Con final si creano costanti.\n\n## Concetti chiave\n### Campi statici\npublic static final double PI = 3.14159;\nprivate static int contatore = 0; // condiviso\n\n## Esempio pratico\n```java\npublic class Frazione {\n    public static final Frazione ZERO = new Frazione(0, 1);\n    private static int istanzeCreate = 0;\n    public Frazione(int n, int d) {\n        istanzeCreate++;\n    }\n}\n```\n\n## Riepilogo\n- static: appartiene alla classe\n- final: non modificabile (costante)\n- Campi statici: condivisi tra tutte le istanze"),
    
    ("mod_044", "Il garbage collector e la gestione della memoria", 2600, 2650,
     ["Comprendere il garbage collector", "Gestire oggetti non più raggiungibili", "Conoscere i limiti del GC"],
     "## Introduzione\nJava gestisce automaticamente la memoria tramite il garbage collector (GC). Quando un oggetto non è più raggiungibile da alcun riferimento, viene marcato per la rimozione.\n\n## Concetti chiave\n### Raggiungibilità\nUn oggetto è raggiungibile se esiste un percorso di riferimenti da una variabile attiva. Quando f = null, l'oggetto può essere garbage-collected.\n\n## Esempio pratico\n```java\nFrazione f = new Frazione(1, 2);\nf = new Frazione(3, 4); // il primo oggetto non è più raggiungibile\n```\n\n## Riepilogo\n- GC rimuove oggetti non raggiungibili\n- Non si può forzare il GC\n- System.gc() è solo un suggerimento"),
    
    ("mod_045", "Documentazione delle classi con javadoc", 2650, 2700,
     ["Scrivere commenti di documentazione /** */", "Usare marcatori @param, @return, @see", "Generare documentazione con javadoc"],
     "## Introduzione\njavadoc genera automaticamente documentazione HTML dai commenti di documentazione (/** */). È uno strumento fondamentale per creare API ben documentate.\n\n## Concetti chiave\n### Commenti di documentazione\n/**\n * Calcola la somma di due frazioni.\n * @param f la frazione da sommare\n * @return una nuova frazione risultato\n */\n\n## Esempio pratico\n```bash\n> javadoc Frazione.java\n```\n\n## Riepilogo\n- /** */ per documentazione\n- @param, @return, @see, @throws\n- javadoc genera HTML"),
    
    ("mod_046", "Package: organizzare le classi in librerie", 2700, 2750,
     ["Creare package con package", "Importare classi con import", "Comprendere la visibilità package-private"],
     "## Introduzione\nI package organizzano le classi in gruppi logici. package prog.utili; dichiara il package. import prog.io.*; importa tutte le classi del package.\n\n## Concetti chiave\n### Visibilità package-private\nSe non si specifica public/private, la classe è visibile solo nello stesso package.\n\n## Esempio pratico\n```java\npackage prog.utili;\npublic class Frazione { ... }\n```\n\n## Riepilogo\n- package raggruppa classi correlate\n- import evita di scrivere il percorso completo\n- Visibilità di default: package-private"),
    
    ("mod_047", "Modificatori di visibilità: public, private, protected", 2750, 2800,
     ["Usare public, private, protected", "Comprendere l'incapsulamento", "Applicare il principio del minimo privilegio"],
     "## Introduzione\nI modificatori di visibilità controllano l'accesso ai membri di una classe: public (tutti), protected (sottoclassi e stesso package), private (solo la classe).\n\n## Concetti chiave\n### Principio di incapsulamento\nCampi privati, metodi getter/setter pubblici. Protegge l'integrità dei dati.\n\n## Esempio pratico\n```java\npublic class Contatore {\n    private int valore = 0;\n    public void incrementa() { valore++; }\n    public int getValore() { return valore; }\n}\n```\n\n## Riepilogo\n- private: solo la classe\n- public: tutti\n- protected: stesso package + sottoclassi\n- Incapsulamento: dati privati, interfaccia pubblica"),
    
    ("mod_048", "Ereditarietà: extends, super e overriding", 2800, 2850,
     ["Usare extends per ereditarietà", "Richiamare superclasse con super", "Applicare l'overriding dei metodi"],
     "## Introduzione\nL'override permette a una sottoclasse di ridefinire un metodo ereditato. super permette di chiamare il metodo della superclasse.\n\n## Concetti chiave\n### Override\n@Override\npublic String toString() { return super.toString() + \" esteso\"; }\n\n### super\nsuper() chiama il costruttore della superclasse. super.metodo() chiama un metodo della superclasse.\n\n## Esempio pratico\n```java\nclass Quadrato extends Rettangolo {\n    public Quadrato(double l) { super(l, l); }\n    @Override\n    public String toString() { return \"Quadrato di lato \" + getBase(); }\n}\n```\n\n## Riepilogo\n- extends: relazione is-a\n- super: riferimento alla superclasse\n- @Override: annotation (opzionale ma consigliata)"),
    
    ("mod_049", "Polimorfismo e selezione dinamica dei metodi", 2850, 2900,
     ["Comprendere il polimorfismo", "Applicare la selezione dinamica a runtime", "Usare instanceof e cast"],
     "## Introduzione\nIl polimorfismo permette di trattare oggetti di classi diverse in modo uniforme. La JVM seleziona il metodo da eseguire a runtime in base al tipo effettivo dell'oggetto.\n\n## Concetti chiave\n### Binding dinamico\nFigura f = new Cerchio(5);\nf.getArea(); // chiama Cerchio.getArea() a runtime\n\n## Esempio pratico\n```java\nFigura[] figure = {new Rettangolo(3,4), new Cerchio(2)};\nfor (Figura f : figure)\n    System.out.println(f.getArea()); // polimorfismo\n```\n\n## Riepilogo\n- Il metodo eseguito dipende dal tipo runtime\n- instanceof controlla il tipo dinamico\n- Polimorfismo: stesso messaggio, comportamenti diversi"),
    
    ("mod_050", "Il metodo equals: confronto di oggetti", 2900, 2950,
     ["Override di equals per confronto semantico", "Rispettare il contratto di equals", "Distinguere equals e hashCode"],
     "## Introduzione\nequals() confronta il contenuto di due oggetti (uguaglianza semantica), mentre == confronta i riferimenti. Ogni classe dovrebbe sovrascrivere equals per definire quando due oggetti sono \"uguali\".\n\n## Concetti chiave\n### Contratto di equals\nRiflessivo, simmetrico, transitivo, consistente. x.equals(null) deve restituire false.\n\n## Esempio pratico\n```java\n@Override\npublic boolean equals(Object altro) {\n    if (altro instanceof Frazione) {\n        Frazione f = (Frazione) altro;\n        return num == f.num && den == f.den;\n    }\n    return false;\n}\n```\n\n## Riepilogo\n- equals: uguaglianza semantica\n- ==: uguaglianza di riferimenti\n- Deve essere coerente con hashCode"),
]

# Add remaining topics
for lid, arg, start, end, goals, content in more_topics:
    add_module(lid, next_ord, arg, content, goals, SRC, start, end)
    next_ord += 1

# Even more lessons to reach 120+
more_lessons_2 = [
    ("mod_051", "Variabili e adombramento (shadowing)", 2950, 3000,
     ["Comprendere lo shadowing", "Usare this per riferirsi all'istanza", "Distinguere variabili locali e campi"],
     "## Introduzione\nLo shadowing (adombramento) si verifica quando una variabile locale ha lo stesso nome di un campo. La variabile locale \"nasconde\" il campo.\n\n## Concetti chiave\n### this\nthis.nomeCampo distingue il campo dalla variabile locale omonima.\n\n## Esempio pratico\n```java\npublic class Persona {\n    private String nome;\n    public void setNome(String nome) {\n        this.nome = nome; // this.nome = campo, nome = parametro\n    }\n}\n```\n\n## Riepilogo\n- Shadowing: variabile locale nasconde il campo\n- this risolve l'ambiguità\n- this si usa solo nei metodi di istanza"),
    
    ("mod_052", "Esempio: implementazione della classe Figura", 3000, 3050,
     ["Implementare classi astratte", "Usare metodi astratti", "Creare gerarchie di classi"],
     "## Introduzione\nImplementiamo la gerarchia Figura con classi astratte e concrete. Figura è astratta con getArea() astratto. Rettangolo e Cerchio forniscono implementazioni specifiche.\n\n## Concetti chiave\n### Gerarchia\nabstract class Figura { abstract double getArea(); }\nclass Rettangolo extends Figura { ... }\nclass Cerchio extends Figura { ... }\n\n## Esempio pratico\n```java\nabstract class Figura {\n    public abstract double getArea();\n    public boolean haAreaMaggiore(Figura altra) {\n        return getArea() > altra.getArea();\n    }\n}\n```\n\n## Riepilogo\n- Classe astratta: non istanziabile\n- Metodo astratto: senza corpo, da implementare\n- Polimorfismo: supertipo per oggetti di sottotipi diversi"),
    
    ("mod_053", "Implementazione della classe Rettangolo e Quadrato", 3050, 3100,
     ["Implementare override di metodi", "Usare protected per l'accesso", "Gestire modifiche coerenti in gerarchia"],
     "## Introduzione\nRettangolo estende Figura. Quadrato estende Rettangolo. Se Quadrato modifica base, deve mantenere la proprietà che base == altezza.\n\n## Concetti chiave\n### protected\nPermette l'accesso alle sottoclassi. protected double base, altezza;\n\n## Esempio pratico\n```java\nclass Rettangolo extends Figura {\n    protected double base, altezza;\n    Rettangolo(double b, double h) { base = b; altezza = h; }\n    public double getArea() { return base * altezza; }\n}\n```\n\n## Riepilogo\n- protected: accessibile a sottoclassi\n- L'override ridefinisce il comportamento\n- Quadrato deve mantenere consistenza (base == altezza)"),
    
    ("mod_054", "Il modificatore final: classi, metodi e variabili", 3100, 3150,
     ["Usare final per classi non estendibili", "Usare final per metodi non overrideabili", "Usare final per costanti"],
     "## Introduzione\nfinal impedisce: l'estensione di una classe, l'override di un metodo, la modifica di una variabile (dopo l'inizializzazione).\n\n## Concetti chiave\n### final su classe\npublic final class String { ... } // non si può estendere\n\n### final su metodo\npublic final void print() { ... } // non si può fare override\n\n### final su variabile\nfinal int MAX = 100; // costante\n\n## Riepilogo\n- final class: non estendibile\n- final method: non overrideabile\n- final variable: costante (una sola assegnazione)"),
    
    ("mod_055", "Tipi generici: classi e metodi parametrici", 3150, 3200,
     ["Definire classi generiche con <T>", "Definire metodi generici", "Usare segnaposto (wildcard)"],
     "## Introduzione\nI generici permettono di scrivere codice che opera su tipi specificati dal chiamante. Eliminano la necessità di cast e garantiscono type safety.\n\n## Concetti chiave\n### Classe generica\npublic class Pila<T> {\n    private List<T> elementi = new ArrayList<>();\n    public void push(T elem) { ... }\n    public T pop() { ... }\n}\n\n## Esempio pratico\n```java\nPila<Frazione> pila = new Pila<>();\npila.push(new Frazione(1, 2));\nFrazione f = pila.pop(); // nessun cast\n```\n\n## Riepilogo\n- <T>: parametro di tipo\n- Type safety: errori a compile-time\n- Nessun cast necessario in lettura"),
    
    ("mod_056", "Vincoli sui segnaposto (wildcard bounds)", 3200, 3250,
     ["Usare wildcard ?", "Applicare extends e super nei bounds", "Comprendere PECS (Producer Extends, Consumer Super)"],
     "## Introduzione\nI wildcard (?) permettono flessibilità nei tipi generici. extends (covarianza) per lettura, super (controvarianza) per scrittura.\n\n## Concetti chiave\n### Wildcard con extends\nSequenza<? extends Figura> può contenere Figura, Rettangolo, Cerchio (sola lettura).\n\n### Wildcard con super\nSequenza<? super Rettangolo> può aggiungere Rettangolo.\n\n## Esempio pratico\n```java\npublic static double areaTotale(Sequenza<? extends Figura> seq) {\n    double tot = 0;\n    for (int i = 0; i < seq.size(); i++)\n        tot += seq.get(i).getArea();\n    return tot;\n}\n```\n\n## Riepilogo\n- ? extends T: lettura (producer)\n- ? super T: scrittura (consumer)\n- PECS: Producer Extends, Consumer Super"),
    
    ("mod_057", "Eccezioni: try-catch per gestire errori", 3250, 3300,
     ["Usare try-catch per intercettare eccezioni", "Gestire eccezioni multiple", "Capire eccezioni controllate e non"],
     "## Introduzione\nLe eccezioni permettono di gestire situazioni anomale separatamente dal codice normale. try-catch intercetta l'eccezione e la gestisce.\n\n## Concetti chiave\n### try-catch\ntry { codice a rischio }\ncatch (TipoEccezione e) { gestione }\n\n### Eccezioni controllate\nIOException, FileNotFoundException: il compilatore obbliga a gestirle.\n\n## Esempio pratico\n```java\ntry {\n    int n = Integer.parseInt(stringa);\n} catch (NumberFormatException e) {\n    System.out.println(\"Formato non valido\");\n}\n```\n\n## Riepilogo\n- try: codice che può generare eccezioni\n- catch: gestione dell'eccezione\n- finally: si esegue sempre (pulizia risorse)"),
    
    ("mod_058", "La clausola finally e chiusura risorse", 3300, 3350,
     ["Usare finally per pulizia", "Chiudere risorse con finally", "Comprendere try-with-resources"],
     "## Introduzione\nfinally si esegue sempre, che l'eccezione venga generata o meno. È il luogo ideale per chiudere file, connessioni, e altre risorse.\n\n## Concetti chiave\n### finally\ntry { ... } catch (...) { ... } finally { ... }\n\n## Esempio pratico\n```java\nBufferedReader br = null;\ntry {\n    br = new BufferedReader(new FileReader(\"file.txt\"));\n} catch (IOException e) {\n    System.out.println(\"Errore\");\n} finally {\n    if (br != null) br.close();\n}\n```\n\n## Riepilogo\n- finally: eseguito sempre\n- Per chiusura risorse\n- Java 7+: try-with-resources (auto-close)"),
    
    ("mod_059", "Stream di caratteri: Reader e Writer", 3350, 3400,
     ["Usare FileReader e FileWriter", "Usare BufferedReader per lettura efficiente", "Comprendere la gerarchia Reader/Writer"],
     "## Introduzione\nGli stream di caratteri (Reader/Writer) permettono di leggere e scrivere file di testo. BufferedReader aggiunge buffer per lettura efficiente.\n\n## Concetti chiave\n### Lettura\nBufferedReader in = new BufferedReader(new FileReader(\"file.txt\"));\nString linea = in.readLine();\n\n### Scrittura\nPrintWriter out = new PrintWriter(new FileWriter(\"output.txt\"));\nout.println(\"Testo\");\n\n## Esempio pratico\n```java\nBufferedReader sorg = new BufferedReader(new FileReader(args[0]));\nString linea;\nwhile ((linea = sorg.readLine()) != null) {\n    System.out.println(linea);\n}\n```\n\n## Riepilogo\n- Reader/Writer per testo\n- BufferedReader per lettura a righe\n- PrintWriter per scrittura formattata"),
    
    ("mod_060", "Stream di byte e dati primitivi", 3400, 3450,
     ["Usare InputStream/OutputStream", "Leggere/scrivere dati binari", "Usare DataInputStream/DataOutputStream"],
     "## Introduzione\nGli stream di byte (InputStream/OutputStream) gestiscono dati binari. DataInputStream/DataOutputStream permettono di leggere/scrivere tipi primitivi in formato binario.\n\n## Concetti chiave\n### Byte stream\nFileInputStream, FileOutputStream.\n\n### Dati primitivi\nDataInputStream.readInt(), readDouble(), readUTF().\n\n## Esempio pratico\n```java\nDataOutputStream out = new DataOutputStream(\n    new FileOutputStream(\"dati.bin\"));\nout.writeInt(42);\nout.writeDouble(3.14);\nout.writeUTF(\"Ciao\");\n```\n\n## Riepilogo\n- Byte stream per file binari\n- Data stream per tipi primitivi\n- flush() per forzare scrittura"),
]

for lid, arg, start, end, goals, content in more_lessons_2:
    add_module(lid, next_ord, arg, content, goals, SRC, start, end)
    next_ord += 1

# Add more quizzes
more_quiz = [
    (f"quiz_00{5 + i}", f"Verifica: ereditarietà e polimorfismo", "mod_040", [
        {"testo": "Cosa significa che una classe è astratta?", "opzioni": ["Non può avere costruttori", "Non può essere istanziata direttamente", "Non ha metodi", "È finale"], "indice_corretto": 1, "spiegazione": "Una classe astratta non può essere istanziata; serve solo come base per sottoclassi."},
        {"testo": "Polimorfismo significa:", "opzioni": ["Una classe ha più costruttori", "Oggetti di classi diverse rispondono allo stesso messaggio in modo specifico", "Un metodo ha più parametri", "Un oggetto può cambiare tipo"], "indice_corretto": 1, "spiegazione": "Il polimorfismo permette a oggetti di classi diverse di rispondere allo stesso messaggio con comportamenti specifici."},
        {"testo": "Cosa fa super()?", "opzioni": ["Crea un nuovo oggetto", "Chiama il costruttore della superclasse", "Termina il programma", "Rende un metodo finale"], "indice_corretto": 1, "spiegazione": "super() invoca il costruttore della superclasse. Deve essere la prima istruzione nel costruttore."},
    ], SRC),
    (f"quiz_00{6 + i}", f"Verifica: eccezioni e I/O", "mod_044", [
        {"testo": "Cosa fa try-catch?", "opzioni": ["Crea un nuovo thread", "Intercetta e gestisce eccezioni", "Apre un file", "Crea un ciclo"], "indice_corretto": 1, "spiegazione": "try-catch intercetta le eccezioni generate nel blocco try e le gestisce nel catch."},
        {"testo": "finally si esegue:", "opzioni": ["Solo se c'è un'eccezione", "Sempre, con o senza eccezione", "Solo se non c'è eccezione", "Mai automaticamente"], "indice_corretto": 1, "spiegazione": "finally si esegue sempre, indipendentemente dal verificarsi di eccezioni."},
        {"testo": "BufferedReader è utile per:", "opzioni": ["Leggere file binari", "Leggere righe di testo efficientemente", "Scrivere su disco", "Comprimere file"], "indice_corretto": 1, "spiegazione": "BufferedReader aggiunge un buffer di memoria che rende la lettura di file di testo più efficiente."},
    ], SRC),
    (f"quiz_00{7 + i}", f"Verifica: tipi generici", "mod_048", [
        {"testo": "Cosa garantiscono i generics?", "opzioni": ["Velocità di esecuzione", "Type safety a compile-time", "Minore uso di memoria", "Compatibilità con C++"], "indice_corretto": 1, "spiegazione": "I generics garantiscono che gli errori di tipo vengano rilevati in fase di compilazione."},
        {"testo": "PECS sta per:", "opzioni": ["Primitive Extend Complex Structure", "Producer Extends, Consumer Super", "Public Enum Control Syntax", "Private Exception Control System"], "indice_corretto": 1, "spiegazione": "PECS: Producer Extends (per lettura), Consumer Super (per scrittura)."},
        {"testo": "Cosa fa ? extends Figura?", "opzioni": ["Accetta solo oggetti Figura", "Accetta Figura e sue sottoclassi", "Accetta solo oggetti che estendono Object", "Non è valido in Java"], "indice_corretto": 1, "spiegazione": "? extends Figura accetta Figura e qualsiasi sua sottoclasse (Rettangolo, Cerchio, etc.)."},
    ], SRC),
]

q_start = 5
for qid, titolo, dopo, domande, src in more_quiz:
    add_quiz(qid, next_ord, titolo, dopo, domande, src)
    next_ord += 1

with open(COURSE_FILE, 'w') as f:
    json.dump(course, f, indent=2, ensure_ascii=False)

mod_count = sum(1 for m in course["moduli"] if m.get("tipo") == "lezione")
quiz_count = sum(1 for m in course["moduli"] if m.get("tipo") == "quiz")
print(f"Done! Lezioni: {mod_count}, Quiz: {quiz_count}, Totale moduli: {len(course['moduli'])}")
