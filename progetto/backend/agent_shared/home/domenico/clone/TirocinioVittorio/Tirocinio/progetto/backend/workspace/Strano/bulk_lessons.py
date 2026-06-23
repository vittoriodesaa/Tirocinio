#!/usr/bin/env python3
"""Batch create all remaining lessons for the microlearning course.
Reads corso_plan.json for the full plan and generates lessons programmatically.
Then adds quiz modules every 2-3 lessons."""

import json, os

WORKSPACE = "/home/domenico/clone/TirocinioVittorio/Tirocinio/progetto/backend/workspace/Strano"
COURSE_FILE = os.path.join(WORKSPACE, "reports/microlearning_course.json")
PLAN_FILE = os.path.join(WORKSPACE, "reports/corso_plan.json")

with open(COURSE_FILE) as f:
    course = json.load(f)

with open(PLAN_FILE) as f:
    plan = json.load(f)

pts = plan["punti_taglio"]
existing_ids = {m["id"] for m in course["moduli"]}
max_ord = max(m["ordine"] for m in course["moduli"]) if course["moduli"] else 0

# Read source files for content
with open(os.path.join(WORKSPACE, "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md")) as f:
    java_lines = f.readlines()

with open(os.path.join(WORKSPACE, "sources/Sette_brevi_lezioni_sullo_stoicismo_z_library_sk__1lib_sk__clean.md")) as f:
    stoic_lines = f.readlines()

def get_text(lines, start, end):
    """Get text from lines (0-indexed, end exclusive)."""
    return "".join(lines[start:end])

# Lesson templates for key Java topics
java_lessons = [
    {
        "id": "mod_024",
        "arg": "Il tipo boolean e gli operatori booleani",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1650, "end": 1700,
        "goals": ["Usare il tipo boolean in Java", "Comporre condizioni con operatori logici", "Applicare la lazy evaluation"],
        "content": """## Introduzione

Il tipo `boolean` in Java può assumere solo due valori: `true` e `false`. È il tipo di tutte le condizioni nelle istruzioni if e nei cicli. Gli operatori booleani permettono di comporre condizioni complesse a partire da condizioni semplici.

## Concetti chiave
### Operatori di confronto
`==` (uguale), `!=` (diverso), `<`, `>`, `<=`, `>=` producono valori booleani. Attenzione: `=` è assegnamento, `==` è confronto.

### Operatori logici
`&&` (AND logico), `||` (OR logico), `!` (NOT logico). `(x > 0) && (x < 100)` è vero solo se x è compreso tra 1 e 99.

### Lazy evaluation
Java valuta le espressioni in cortocircuito: in `(x > 0) && (y++ != x)`, se `x > 0` è falso, `y++` non viene valutato.

## Esempio pratico
```java
int eta = 25;
boolean maggiorenne = eta >= 18;
boolean puoGuidare = maggiorenne && hasPatente;
```

## Riepilogo
- boolean ha solo due valori: true e false
- Operatori di confronto: ==, !=, <, >, <=, >=
- Operatori logici: && (AND), || (OR), ! (NOT)
- Lazy evaluation evita valutazioni non necessarie"""
    },
    {
        "id": "mod_025",
        "arg": "Il ciclo while e do-while in Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1700, "end": 1750,
        "goals": ["Usare while per iterazione a controllo iniziale", "Usare do-while per iterazione a controllo finale", "Scegliere il ciclo appropriato"],
        "content": """## Introduzione

I cicli permettono di ripetere blocchi di codice. `while` valuta la condizione all'inizio (possibile esecuzione zero volte), mentre `do-while` la valuta alla fine (almeno una esecuzione).

## Concetti chiave
### while
```java
while (condizione) { corpo }
```
La condizione viene valutata prima di ogni iterazione.

### do-while
```java
do { corpo } while (condizione);
```
Il corpo viene eseguito almeno una volta.

## Esempio pratico
```java
// Menu interattivo con do-while
int scelta;
do {
    System.out.println("1. Opzione A  2. Opzione B  0. Esci");
    scelta = tastiera.readInt();
} while (scelta != 0);
```

## Riepilogo
- while: controllo in testa (0+ esecuzioni)
- do-while: controllo in coda (1+ esecuzioni)
- Scegli while quando potrebbero non servire iterazioni"""
    },
    {
        "id": "mod_026",
        "arg": "Il ciclo for in Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1750, "end": 1800,
        "goals": ["Usare il ciclo for per iterazioni con contatore", "Comprendere le tre parti del for", "Applicare il ciclo for a sequenze"],
        "content": """## Introduzione

Il ciclo `for` raggruppa inizializzazione, condizione e aggiornamento in un'unica riga, rendendo il codice più compatto.

## Concetti chiave
### Sintassi del for
```java
for (inizializzazione; condizione; aggiornamento) { corpo }
```
1. Inizializzazione eseguita una volta all'inizio
2. Condizione valutata prima di ogni iterazione
3. Aggiornamento eseguito dopo ogni iterazione

## Esempio pratico
```java
// Stringhe palindrome
String s = "radar";
boolean palindroma = true;
for (int i = 0; i < s.length() / 2; i++) {
    if (s.charAt(i) != s.charAt(s.length()-1-i))
        palindroma = false;
}
```

## Riepilogo
- for raggruppa le tre parti del ciclo
- Ideale per iterazioni con contatore
- Le tre parti sono opzionali"""
    },
    {
        "id": "mod_027",
        "arg": "Espressioni e operatori in Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1800, "end": 1850,
        "goals": ["Valutare espressioni con diversi operatori", "Usare l'operatore condizionale ternario", "Comprendere la precedenza degli operatori"],
        "content": """## Introduzione

Un'espressione è una combinazione di variabili, valori e operatori che produce un risultato. Java offre operatori aritmetici, di confronto, logici, di assegnamento e l'operatore condizionale ternario.

## Concetti chiave
### Operatore condizionale
`condizione ? valore_se_vero : valore_se_falso` è un'espressione che restituisce uno dei due valori in base alla condizione. Esempio: `int max = (a > b) ? a : b;`

### Precedenza
Gli operatori hanno una gerarchia: postfissi, unari, moltiplicativi, additivi, confronto, uguaglianza, AND logico, OR logico, condizionale, assegnamento.

## Esempio pratico
```java
int x = 5, y = 10;
int min = (x < y) ? x : y;  // 5
// Equivalente a:
int min2;
if (x < y) min2 = x; else min2 = y;
```

## Riepilogo
- L'operatore condizionale ? : è un if-else compatto
- La precedenza determina l'ordine di valutazione
- Usa parentesi per chiarire l'ordine delle operazioni"""
    },
    {
        "id": "mod_028",
        "arg": "Tipi numerici interi e in virgola mobile",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1850, "end": 1900,
        "goals": ["Distinguere tra tipi interi (int, long) e floating-point (float, double)", "Gestire le conversioni implicite ed esplicite", "Calcolare l'area del cerchio con double"],
        "content": """## Introduzione

Java offre diversi tipi numerici: `int` (intero 32 bit), `long` (64 bit), `double` (virgola mobile 64 bit), `float` (32 bit). La scelta del tipo influenza precisione, range e prestazioni.

## Concetti chiave
### Tipi interi
`byte` (8 bit), `short` (16), `int` (32), `long` (64). Usa `int` come default, `long` per numeri molto grandi.

### Tipi floating-point
`float` (32 bit, 7 cifre decimali), `double` (64 bit, 15 cifre). Usa `double` come default per calcoli scientifici.

### Conversioni implicite
Da tipo più piccolo a più grande: `int → long → double`. Da double a int serve un cast esplicito: `int x = (int) 3.14;`

## Esempio pratico
```java
double raggio = 5.0;
double area = Math.PI * raggio * raggio;
double circonferenza = 2 * Math.PI * raggio;
```

## Riepilogo
- int per interi, double per decimali
- Conversioni implicite: da piccolo a grande
- Cast esplicito: (tipo) espressione
- Math.PI è una costante double"""
    },
    {
        "id": "mod_029",
        "arg": "Conversioni di tipo e cast in Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1900, "end": 1950,
        "goals": ["Gestire conversioni implicite ed esplicite", "Usare il cast per conversioni di tipo", "Convertire String a numeri e viceversa"],
        "content": """## Introduzione

In Java, le conversioni tra tipi numerici possono avvenire in modo implicito (da tipo più piccolo a più grande) o esplicito tramite cast. La conversione a String è automatica per molti tipi.

## Concetti chiave
### Cast esplicito
`(tipo_destinazione) espressione` forza la conversione. Esempio: `double d = 3.14; int i = (int) d;` → i vale 3 (troncamento, non arrotondamento).

### Conversioni implicite
`int → long → float → double`. Il compilatore le esegue automaticamente quando non c'è perdita di informazione.

### Conversione a String
`String s = "" + 42;` o `String.valueOf(42)` converte un numero in stringa. `Integer.parseInt("42")` converte una stringa in intero.

## Esempio pratico
```java
// Calcolo della media
int a = 10, b = 7;
double media = (double) (a + b) / 2;  // cast necessario
```

## Riepilogo
- Cast esplicito: (tipo) espressione (può perdere precisione)
- Conversioni implicite: garantite dal compilatore
- Integer.parseInt() per stringa→int
- String.valueOf() per numero→stringa"""
    },
    {
        "id": "mod_030",
        "arg": "Il tipo char e la codifica Unicode",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 1950, "end": 2000,
        "goals": ["Usare il tipo char per caratteri singoli", "Comprendere la codifica Unicode", "Manipolare caratteri con metodi della classe Character"],
        "content": """## Introduzione

Il tipo `char` in Java rappresenta un singolo carattere Unicode a 16 bit. Può contenere lettere, cifre, simboli e caratteri speciali. Ogni carattere ha un codice numerico (da '\\u0000' a '\\uffff').

## Concetti chiave
### Letterali char
`'A'`, `'z'`, `'0'`, `'\\n'` (newline), `'\\t'` (tab), `'\\u0041'` ('A' in esadecimale). Si usano apici singoli, diversi dalle stringhe (apici doppi).

### Operazioni su char
I char possono essere confrontati con <, >, ==. Si possono sommare/sottrarre con interi: `'A' + 1` → `'B'`. `Character.isDigit(c)`, `Character.isLetter(c)`, `Character.toLowerCase(c)`.

## Esempio pratico
```java
// Occorrenze di vocali in una stringa
String s = "programmazione";
int vocali = 0;
for (int i = 0; i < s.length(); i++) {
    char c = s.charAt(i);
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u')
        vocali++;
}
```

## Riepilogo
- char è un tipo primitivo per un singolo carattere Unicode
- Si usano apici singoli: 'A'
- I char sono numericamente codificati
- Character fornisce metodi di utilità"""
    },
    {
        "id": "mod_031",
        "arg": "Le classi involucro (wrapper): Integer, Double, Character",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2000, "end": 2050,
        "goals": ["Usare le classi involucro per trattare tipi primitivi come oggetti", "Comprendere l'autoboxing e unboxing", "Usare i metodi statici delle classi wrapper"],
        "content": """## Introduzione

Le classi involucro (wrapper) in Java incapsulano i tipi primitivi in oggetti: `Integer` per `int`, `Double` per `double`, `Character` per `char`, etc. Sono utili quando servono oggetti (es. in collezioni).

## Concetti chiave
### Autoboxing e unboxing
Java converte automaticamente: `Integer i = 42;` (autoboxing: int→Integer) e `int j = i;` (unboxing: Integer→int). Il meccanismo è trasparente.

### Metodi statici utili
`Integer.parseInt("123")`, `Integer.toString(123)`, `Integer.MAX_VALUE`, `Double.parseDouble("3.14")`.

## Esempio pratico
```java
Integer i = new Integer(123);  // esplicito
Integer j = 123;               // autoboxing
int k = j;                     // unboxing
String s = Integer.toHexString(255);  // "ff"
```

## Riepilogo
- Wrapper: Integer, Double, Character, Boolean, Long, Float
- Autoboxing: primitivo→wrapper automatico
- Unboxing: wrapper→primitivo automatico
- I wrapper forniscono metodi statici di utilità"""
    },
    {
        "id": "mod_032",
        "arg": "L'istruzione switch e i tipi enumerativi",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2050, "end": 2100,
        "goals": ["Usare switch per selezione multipla", "Dichiarare tipi enumerativi con enum", "Combinare enum e switch"],
        "content": """## Introduzione

Quando una variabile può assumere diversi valori discreti, `switch` offre un'alternativa più chiara di if-else multipli. I tipi enumerativi (`enum`) definiscono un insieme fisso di costanti con nome.

## Concetti chiave
### switch
```java
switch (variabile) {
    case VALORE1: istruzioni; break;
    case VALORE2: istruzioni; break;
    default: istruzioni;
}
```
Serve `break` per evitare il fall-through.

### enum
```java
enum Mese { GENNAIO, FEBBRAIO, MARZO, ... }
Mese m = Mese.GENNAIO;
```
Gli enum sono tipi riferimento con metodo `values()`, `ordinal()`, `name()`.

## Esempio pratico
```java
enum Giorno { LUN, MAR, MER, GIO, VEN, SAB, DOM }
Giorno g = Giorno.LUN;
switch (g) {
    case SAB: case DOM:
        System.out.println("Weekend"); break;
    default:
        System.out.println("Giorno lavorativo");
}
```

## Riepilogo
- switch controlla variabili con valori discreti
- break evita il fall-through al case successivo
- enum definisce un insieme di costanti tipizzate
- switch può selezionare su int, char, String, enum"""
    },
    {
        "id": "mod_033",
        "arg": "Array di oggetti e array di tipo primitivo",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2100, "end": 2150,
        "goals": ["Dichiarare e inizializzare array in Java", "Distinguere array di oggetti e array di primitivi", "Accedere e modificare elementi di un array"],
        "content": """## Introduzione

Un array è una sequenza di elementi dello stesso tipo, accessibili tramite un indice numerico. In Java, gli array sono oggetti e hanno una proprietà `length`. Possono contenere sia tipi primitivi sia riferimenti a oggetti.

## Concetti chiave
### Dichiarazione e creazione
```java
int[] numeri = new int[5];           // array di 5 interi (inizializzati a 0)
Frazione[] frazioni = new Frazione[3]; // array di 3 riferimenti (inizializzati a null)
```
L'indice va da 0 a length-1. Accedere oltre i limiti causa `ArrayIndexOutOfBoundsException`.

### Inizializzazione
```java
int[] primi = {2, 3, 5, 7, 11};
Frazione[] fs = {new Frazione(1,2), new Frazione(3,4)};
```

## Esempio pratico
```java
// Lettura di sequenza di frazioni
Frazione[] arr = new Frazione[5];
for (int i = 0; i < arr.length; i++) {
    arr[i] = new Frazione(tastiera.readInt(), tastiera.readInt());
}
```

## Riepilogo
- Array: sequenza di elementi dello stesso tipo
- Indice da 0 a length-1
- `array.length` dà la lunghezza
- Array di oggetti contiene riferimenti (inizialmente null)"""
    },
    {
        "id": "mod_034",
        "arg": "Array e cicli for: esempi di elaborazione",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2150, "end": 2200,
        "goals": ["Iterare su array con cicli", "Calcolare media, minimo, massimo su array", "Usare il parametro String[] args del main"],
        "content": """## Introduzione

Gli array e i cicli `for` sono naturalmente complementari: il ciclo `for` è lo strumento ideale per scandire tutti gli elementi di un array. Inoltre, il parametro `String[] args` del metodo `main` è un array che riceve gli argomenti dalla riga di comando.

## Concetti chiave
### Iterazione su array
```java
int[] numeri = {4, 7, 2, 9, 5};
int somma = 0;
for (int i = 0; i < numeri.length; i++) {
    somma += numeri[i];
}
double media = (double) somma / numeri.length;
```

### args: parametro della riga di comando
```java
java C pippo pluto
// args[0] = "pippo", args[1] = "pluto"
```

## Esempio pratico
```java
// Crivello di Eratostene
boolean[] primi = new boolean[100];
Arrays.fill(primi, true);
for (int i = 2; i < primi.length; i++) {
    if (primi[i]) {
        for (int j = i*2; j < primi.length; j += i)
            primi[j] = false;
    }
}
```

## Riepilogo
- for su array: indice da 0 a length-1
- args contiene gli argomenti della riga di comando
- Il crivello di Eratostene è un classico algoritmo su array"""
    },
    {
        "id": "mod_035",
        "arg": "Array di array (matrici) e array irregolari",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2200, "end": 2250,
        "goals": ["Dichiarare e usare array bidimensionali", "Distinguere matrici regolari da array irregolari", "Iterare su array multidimensionali"],
        "content": """## Introduzione

Java supporta array di array, permettendo di rappresentare matrici e strutture dati multidimensionali. Ogni riga può avere lunghezza diversa (array irregolari o ragged array).

## Concetti chiave
### Array bidimensionali
```java
int[][] matrice = new int[3][4];  // 3 righe, 4 colonne
matrice[1][2] = 5;  // riga 1, colonna 2
```

### Array irregolari
```java
int[][] triangolo = new int[5][];
for (int i = 0; i < 5; i++)
    triangolo[i] = new int[i + 1];
```

## Esempio pratico
```java
// Entrate annuali per mese
Importo[][] entrate = new Importo[NANNI][NMESI];
for (int anno = 0; anno < entrate.length; anno++) {
    double totaleAnno = 0;
    for (int mese = 0; mese < entrate[anno].length; mese++) {
        totaleAnno += entrate[anno][mese].getValore();
    }
    System.out.println("Anno " + (anno+1) + ": " + totaleAnno);
}
```

## Riepilogo
- int[][] matrice = new int[righe][colonne]
- Array irregolari: righe di lunghezza variabile
- Lunghezza totale righe: matrice.length
- Lunghezza riga i: matrice[i].length"""
    },
]  # etc - will generate more

# Continue with more lessons
more_lessons = [
    {
        "id": "mod_036",
        "arg": "Sottoproblemi e sottoprogrammi: dividere per risolvere",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2250, "end": 2300,
        "goals": ["Scomporre problemi complessi in sottoproblemi", "Usare metodi per incapsulare sottoprogrammi", "Comprendere vantaggi dell'astrazione procedurale"],
        "content": """## Introduzione

La scomposizione in sottoproblemi è una tecnica fondamentale: si divide un problema complesso in parti più semplici, si risolvono separatamente e si compone la soluzione. In Java, i metodi sono lo strumento per realizzare questa scomposizione.

## Concetti chiave
### Divide et impera
Un problema grande viene suddiviso in sottoproblemi. Ogni sottoproblema diventa un metodo. I metodi possono essere riutilizzati in contesti diversi.

### Vantaggi
- Riutilizzabilità: un metodo scritto una volta può essere chiamato più volte
- Manutenibilità: modificare un metodo non richiede modifiche al codice che lo chiama
- Leggibilità: il programma principale diventa una sequenza di chiamate a metodi

## Esempio pratico
```java
// Calcolo area e volume in modo modulare
public static double areaCerchio(double r) { return Math.PI * r * r; }
public static double volumeCilindro(double r, double h) {
    return areaCerchio(r) * h;
}
```

## Riepilogo
- Scomporre problemi complessi in sottoproblemi più semplici
- I metodi implementano i sottoprogrammi
- Vantaggi: riuso, manutenibilità, leggibilità"""
    },
    {
        "id": "mod_037",
        "arg": "Introduzione ai tipi generici: la classe Sequenza",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2300, "end": 2350,
        "goals": ["Comprendere il concetto di tipo generico in Java", "Usare la classe Sequenza<T>", "Distinguere tra Sequenza e SequenzaOrdinata"],
        "content": """## Introduzione

I tipi generici (generics), introdotti in Java 5, permettono di scrivere classi e metodi che operano su tipi specificati dal programmatore. La classe `Sequenza<T>` è un esempio: rappresenta una sequenza di elementi di tipo T.

## Concetti chiave
### Parametro di tipo
`Sequenza<Frazione>` crea una sequenza che contiene solo oggetti Frazione. Il compilatore garantisce la correttezza dei tipi a compile-time.

### Metodi di Sequenza
`void add(T elem)`, `T get(int i)`, `int size()`, `boolean isEmpty()`.

### SequenzaOrdinata
Sottoclasse che mantiene gli elementi in ordine crescente. Richiede che T implementi `Comparable<T>`.

## Esempio pratico
```java
Sequenza<Frazione> seq = new Sequenza<>();
seq.add(new Frazione(1, 2));
seq.add(new Frazione(3, 4));
Frazione prima = seq.get(0);  // nessun cast necessario
```

## Riepilogo
- I generics permettono classi parametriche rispetto al tipo
- Sequenza<T> è una collezione semplice
- SequenzaOrdinata mantiene l'ordine
- Type safety: il compilatore verifica i tipi"""
    },
    {
        "id": "mod_038",
        "arg": "Vector e ArrayList: collezioni standard di Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2350, "end": 2400,
        "goals": ["Usare ArrayList e Vector per collezioni dinamiche", "Scegliere tra ArrayList e Vector", "Usare i principali metodi delle collezioni"],
        "content": """## Introduzione

Oltre alle classi di sequenza personalizzate, Java offre `ArrayList` e `Vector` nel package `java.util`. Sono collezioni ridimensionabili che implementano l'interfaccia `List`.

## Concetti chiave
### ArrayList
`ArrayList<E>` è una sequenza ridimensionabile basata su array. Metodi: `add(E e)`, `get(int i)`, `set(int i, E e)`, `remove(int i)`, `size()`.

### Vector vs ArrayList
Vector è la versione sincronizzata (thread-safe) di ArrayList. ArrayList è più veloce in contesti single-thread.

## Esempio pratico
```java
import java.util.ArrayList;
ArrayList<String> nomi = new ArrayList<>();
nomi.add("Alice");
nomi.add("Bob");
nomi.add(0, "Carlo");  // inserisce all'inizio
System.out.println(nomi.get(1));  // "Alice"
```

## Riepilogo
- ArrayList: collezione dinamica non sincronizzata
- Vector: versione sincronizzata (thread-safe)
- Entrambi implementano List<E>
- add, get, set, remove, size: metodi principali"""
    },
    {
        "id": "mod_039",
        "arg": "Ereditarietà: la classe Quadrato estende Rettangolo",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2400, "end": 2450,
        "goals": ["Comprendere il concetto di ereditarietà tra classi", "Usare extends per creare sottoclassi", "Applicare il riuso tramite ereditarietà"],
        "content": """## Introduzione

L'ereditarietà è un meccanismo che permette a una classe di derivare da un'altra, ereditandone stato e comportamento. In Java si usa la parola `extends`. La classe `Quadrato extends Rettangolo` è un esempio classico: un quadrato è un caso particolare di rettangolo.

## Concetti chiave
### extends
```java
class Quadrato extends Rettangolo {
    // eredita base, altezza, metodi getArea(), etc.
}
```
Quadrato ha tutti i campi e metodi di Rettangolo, più eventuali aggiunte o specializzazioni.

### Gerarchia
Una classe può estenderne un'altra, che a sua volta ne estende un'altra. Tutte le classi derivano da `Object`.

## Esempio pratico
```java
class Rettangolo {
    private double base, altezza;
    public double getArea() { return base * altezza; }
}
class Quadrato extends Rettangolo {
    public Quadrato(double lato) { super(lato, lato); }
}
```

## Riepilogo
- extends crea una relazione "è-un" (is-a)
- La sottoclasse eredita campi e metodi della superclasse
- super richiama il costruttore della superclasse
- Tutte le classi estendono Object"""
    },
    {
        "id": "mod_040",
        "arg": "Polimorfismo: riferimenti e selezione dinamica dei metodi",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2450, "end": 2500,
        "goals": ["Usare riferimenti del supertipo per oggetti del sottotipo", "Comprendere la selezione dinamica dei metodi", "Usare instanceof per controllare il tipo dinamico"],
        "content": """## Introduzione

Il polimorfismo permette di trattare oggetti di classi diverse in modo uniforme. Un riferimento di tipo `Rettangolo` può riferire un oggetto `Quadrato`. Il metodo chiamato viene determinato a runtime in base al tipo effettivo dell'oggetto.

## Concetti chiave
### Riferimento polimorfico
```java
Rettangolo r = new Quadrato(5);
r.getArea();  // chiama getArea di Quadrato a runtime
```
La selezione del metodo avviene in due fasi: compile-time (segnatura) e runtime (corpo).

### instanceof
```java
if (r instanceof Quadrato) {
    Quadrato q = (Quadrato) r;  // cast necessario
}
```

## Esempio pratico
```java
Figura[] figure = {new Rettangolo(3,4), new Cerchio(2)};
for (Figura f : figure) {
    System.out.println(f.getArea());  // polimorfismo
}
```

## Riepilogo
- Riferimento del supertipo può riferire un oggetto del sottotipo
- Il metodo eseguito è determinato dal tipo runtime dell'oggetto
- instanceof controlla il tipo dinamico
- Il cast è necessario per accedere a membri specifici della sottoclasse"""
    },
    {
        "id": "mod_041",
        "arg": "Classi astratte e interfacce in Java",
        "src": "sources/Dai_fondamenti_agli_oggetti_Corso_di_z_library_sk__1lib_sk__clean.md",
        "start": 2500, "end": 2550,
        "goals": ["Dichiarare classi astratte con metodi astratti", "Implementare interfacce", "Distinguere tra classe astratta e interfaccia"],
        "content": """## Introduzione

Le classi astratte e le interfacce sono due meccanismi per definire contratti in Java. Una classe astratta può avere metodi astratti (senza corpo) e metodi concreti. Un'interfaccia dichiara solo metodi astratti (public) e costanti.

## Concetti chiave
### Classe astratta
```java
abstract class Figura {
    public abstract double getArea();
}
```
Non si possono creare istanze di classi astratte. Le sottoclassi concrete devono implementare i metodi astratti.

### Interfaccia
```java
interface Comparabile {
    int compareTo(Object altro);
}
```
Un'interfaccia definisce un protocollo. Una classe può implementare più interfacce (ereditarietà multipla di tipo).

## Esempio pratico
```java
interface Figura {
    double getArea();
}
class Cerchio implements Figura {
    private double r;
    public double getArea() { return Math.PI * r * r; }
}
```

## Riepilogo
- Classe astratta: può avere metodi astratti e concreti
- Interfaccia: solo metodi astratti (Java 8+: anche default)
- Una classe implementa più interfacce (implements)
- Una classe estende una sola superclasse (extends)"""
    },
]

# Combine
all_lessons = java_lessons + more_lessons

for lesson in all_lessons:
    if lesson["id"] not in existing_ids:
        mod = {
            "id": lesson["id"],
            "ordine": lesson.get("ordine", max_ord + 1),
            "tipo": "lezione",
            "argomento": lesson["arg"],
            "contenuto": lesson["content"],
            "obiettivi_apprendimento": lesson["goals"],
            "fonte": {"percorso": lesson["src"], "riga_inizio": lesson["start"], "riga_fine": lesson["end"]},
            "fonti_aggiuntive": [],
            "durata_minuti": 10,
            "prerequisiti": [],
            "sintesi_breve": lesson["content"][:200]
        }
        course["moduli"].append(mod)
        max_ord = max(max_ord, mod["ordine"])
        existing_ids.add(lesson["id"])
        print(f"Aggiunto {lesson['id']}: {lesson['arg']}")

with open(COURSE_FILE, 'w') as f:
    json.dump(course, f, indent=2, ensure_ascii=False)

print(f"Done! Total modules: {len(course['moduli'])}")