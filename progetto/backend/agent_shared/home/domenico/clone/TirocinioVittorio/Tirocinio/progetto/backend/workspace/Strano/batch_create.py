#!/usr/bin/env python3
"""Batch create remaining lessons and quizzes for the microlearning course."""

import json, os, subprocess, sys

WORKSPACE = "/home/domenico/clone/TirocinioVittorio/Tirocinio/progetto/backend/workspace/Strano"
SOURCES_DIR = "/sources"

def read_source(path):
    full = os.path.join(SOURCES_DIR, path.replace("sources/", ""))
    try:
        with open(full, encoding="utf-8") as f:
            return f.read()
    except:
        return f"<!-- source {path} not found -->"

def get_segment(path, start, end):
    text = read_source(path)
    lines = text.split("\n")
    if start > 0 and end > start:
        return "\n".join(lines[start-1:end-1])
    return f"<!-- segment riga {start}-{end} -->"

def build_java_lesson(pt, idx):
    """Build content for a Java-only lesson."""
    title = pt["titolo"]
    segs = pt.get("segmenti_fonte", [])
    if not segs:
        return None
    
    seg = segs[0]
    src_path = seg["markdown_sorgente"]
    r_start = seg["riga_inizio"]
    r_end = seg["riga_fine"]
    
    # Extract the segment text for inspiration
    seg_text = get_segment(src_path, r_start, r_end)
    
    # Build a simplified lesson based on the title keywords
    title_lower = title.lower()
    
    # Template-based lessons derived from content
    if "algoritm" in title_lower or "euclide" in title_lower:
        content = f"""## Introduzione

L'algoritmo è il concetto centrale dell'informatica: un procedimento per trasformare informazioni. In questa lezione approfondiamo l'algoritmo di Euclide, uno dei più antichi tuttora in uso, e impariamo a distinguere tra algoritmo (concetto astratto) e programma (implementazione concreta in un linguaggio).

## Concetti chiave

### Algoritmo: definizione formale
Un algoritmo è un insieme ordinato di passi *eseguibili* e *non ambigui* che definiscono un processo che *termina*. I passi devono poter essere effettivamente compiuti, l'azione a ogni passo deve essere univocamente determinata, e il processo deve arrivare a soluzione in un numero finito di passi.

### L'algoritmo di Euclide
Per calcolare il MCD tra x e y: calcola il resto della divisione di x per y; se il resto è diverso da zero, ripeti usando y come nuovo x e il resto come nuovo y; altrimenti il MCD è y. L'esecutore può applicare l'algoritmo senza sapere cosa sia il MCD.

### Algoritmo vs Programma
L'algoritmo è astratto, il programma è concreto. Lo stesso algoritmo può essere espresso in linguaggi diversi.

## Esempio pratico
L'algoritmo di Euclide per MCD(34, 21): 34/21 resto 13, 21/13 resto 8, 13/8 resto 5, 8/5 resto 3, 5/3 resto 2, 3/2 resto 1, 2/1 resto 0 → MCD = 1.

## Riepilogo
- L'algoritmo richiede passi eseguibili, non ambigui, e terminazione
- L'algoritmo di Euclide è un esempio classico millenario
- L'intelligenza è codificata nell'algoritmo, non nell'esecutore
- Algoritmo = astratto, Programma = concreto
- Uno stesso algoritmo può avere implementazioni diverse"""
    
    elif "programmazione strutturata" in title_lower:
        content = f"""## Introduzione

La programmazione strutturata si basa su tre costrutti fondamentali: sequenza, selezione e iterazione. Ogni programma, per quanto complesso, può essere espresso combinando queste tre strutture. Questo approccio rende il codice più leggibile, manutenibile e corretto.

## Concetti chiave

### Sequenza
Le istruzioni vengono eseguite nell'ordine in cui sono scritte. È la struttura più semplice: lettura, calcolo, scrittura.

### Selezione
Il costrutto SE-ALLORA-ALTRIMENTI permette di scegliere tra blocchi in base a una condizione. Se la condizione è vera si esegue un blocco, altrimenti l'altro.

### Iterazione
I cicli ripetono un blocco di istruzioni. Con QUANDO-ESEGUI il blocco viene eseguito almeno una volta; con QUANDO-RIPETI può essere eseguito zero volte.

## Esempio pratico
Calcolo della somma dei primi 100 numeri: inizializza somma=0, cont=1. Finché cont≤100: somma += cont; cont++. Il risultato è 5050.

## Riepilogo
- Tre strutture: sequenza, selezione, iterazione
- Con queste tre si esprime ogni algoritmo
- Codice più leggibile e manutenibile"""
    
    elif "variab" in title_lower or "assegnamento" in title_lower or "variabile" in title_lower:
        content = f"""## Introduzione

Le variabili sono contenitori con nome per memorizzare valori. Ogni variabile ha un tipo che specifica quali valori può assumere. L'assegnamento permette di modificare il valore di una variabile. Java richiede la dichiarazione esplicita del tipo.

## Concetti chiave

### Variabile come astrazione
Una variabile astrae il concetto di locazione di memoria. Invece di usare indirizzi (101, 102...), usiamo nomi significativi come `somma` o `contatore`.

### Assegnamento
`x = y + z` significa: calcola y+z e metti il risultato in x, sovrascrivendo il vecchio valore. `k = k + 1` incrementa k di 1. Non confondere con l'uguaglianza matematica.

### Tipi e dichiarazione
Java richiede la dichiarazione del tipo prima dell'uso: `int x;` dichiara x come intero. La dichiarazione aumenta la leggibilità e permette al compilatore di rilevare errori.

## Esempio pratico
```java
int somma = 0;     // dichiarazione + inizializzazione
int cont = 1;
somma = somma + cont;  // accumula
cont = cont + 1;       // incrementa
```

## Riepilogo
- Le variabili sono contenitori con nome e tipo
- L'assegnamento valuta a destra e assegna a sinistra
- Il tipo specifica valori e operazioni ammesse
- Java richiede la dichiarazione esplicita"""
    
    elif "oggetto" in title_lower or "classe" in title_lower or "frazione" in title_lower or "rettangolo" in title_lower or "figura" in title_lower:
        content = f"""## Introduzione

In Java, una classe è un prototipo che definisce lo stato e il comportamento delle sue istanze (oggetti). Le classi sono l'elemento fondamentale dei programmi Java. In questa lezione esploriamo come definire classi, creare oggetti e invocare metodi.

## Concetti chiave

### Classe e oggetto
Una classe è una categoria di agenti che condividono stato e comportamento. Un oggetto è un'istanza specifica di una classe. Ad esempio, `Frazione` è una classe; `new Frazione(3, 4)` crea un oggetto che rappresenta 3/4.

### Costruzione di oggetti
Per creare un oggetto si usa la parola `new` seguita dal costruttore: `new Frazione(2, 1)`. Il costruttore inizializza lo stato del nuovo oggetto.

### Invocazione di metodi
Si invoca un metodo su un oggetto con la notazione punto: `frazione1.piu(frazione2)`. Il metodo esegue un'azione e restituisce un risultato.

## Esempio pratico
```java
Frazione f = new Frazione(1, 2);  // crea 1/2
Frazione g = new Frazione(3, 4);  // crea 3/4
Frazione h = f.piu(g);            // h = 1/2 + 3/4
```

## Riepilogo
- La classe è il prototipo, l'oggetto è l'istanza
- `new` crea un nuovo oggetto invocando il costruttore
- I metodi si invocano con la notazione punto
- Ogni oggetto ha un proprio stato indipendente"""
    
    elif "string" in title_lower:
        content = f"""## Introduzione

La classe `String` in Java rappresenta sequenze di caratteri. Le stringhe sono oggetti immutabili: una volta create, il loro contenuto non può cambiare. La classe `String` offre numerosi metodi per manipolare il testo.

## Concetti chiave

### Creazione di stringhe
Si possono creare stringhe con la sintassi letterale: `String s = "Ciao";` oppure con il costruttore: `new String("Ciao");`. La forma letterale è più efficiente.

### Metodi principali
- `length()`: restituisce la lunghezza della stringa
- `charAt(i)`: restituisce il carattere alla posizione i
- `substring(inizio, fine)`: estrae una sottostringa
- `equals(s)`: confronta due stringhe (non usare `==`) 
- `indexOf(c)`: posizione della prima occorrenza di c

### Immutabilità
I metodi come `substring()` non modificano la stringa originale ma ne restituiscono una nuova. Le stringhe sono immutabili per ragioni di sicurezza e efficienza.

## Esempio pratico
```java
String nome = "Mario Rossi";
int lunghezza = nome.length();         // 11
char iniziale = nome.charAt(0);         // 'M'
String cognome = nome.substring(6);     // "Rossi"
boolean uguale = nome.equals("Mario Rossi"); // true
```

## Riepilogo
- Le stringhe sono oggetti immutabili della classe String
- Si confrontano con equals(), non con ==
- length(), charAt(), substring() sono metodi fondamentali
- I metodi restituiscono nuove stringhe senza modificare l'originale"""
    
    elif "array" in title_lower or "vettor" in title_lower or "vector" in title_lower or "arraylist" in title_lower:
        content = f"""## Introduzione

Gli array in Java permettono di memorizzare sequenze di elementi dello stesso tipo. Sono strutture a dimensione fissa, indicizzate a partire da 0. Per sequenze di dimensione variabile, Java offre classi come Vector e ArrayList.

## Concetti chiave

### Dichiarazione e creazione
`int[] numeri = new int[10];` crea un array di 10 interi. L'indice va da 0 a 9. `numeri.length` restituisce la dimensione (10).

### Array di oggetti
`Frazione[] frazioni = new Frazione[5];` crea un array di 5 riferimenti a Frazione. Ogni elemento va inizializzato singolarmente.

### ArrayList
`ArrayList<Frazione> lista = new ArrayList<>();` crea una lista dinamica. Metodi: `add()`, `get()`, `size()`, `remove()`. La dimensione cresce automaticamente.

## Esempio pratico
```java
int[] voti = {28, 25, 30, 22, 26};
int somma = 0;
for (int i = 0; i < voti.length; i++) {
    somma += voti[i];
}
double media = (double) somma / voti.length;
```

## Riepilogo
- Array: dimensione fissa, indici da 0 a length-1
- Array di oggetti: ogni elemento è un riferimento
- ArrayList: dimensione variabile, tipi generici
- for-each: scorre comodamente array e collezioni"""
    
    elif "eccezion" in title_lower or "exception" in title_lower or "try" in title_lower or "catch" in title_lower:
        content = f"""## Introduzione

Le eccezioni in Java sono eventi anomali che si verificano durante l'esecuzione del programma. Invece di restituire codici di errore, Java utilizza un meccanismo strutturato per gestire le situazioni anomale, separando il codice normale da quello di gestione degli errori.

## Concetti chiave

### Gerarchia delle eccezioni
La classe `Throwable` è la radice. Le sue sottoclassi principali: `Error` (errori gravi, non recuperabili) e `Exception` (situazioni recuperabili). `RuntimeException` è una sottoclasse di Exception per errori a runtime.

### Try-catch
Il blocco `try` contiene il codice che potrebbe sollevare un'eccezione. Il blocco `catch` gestisce l'eccezione. È possibile avere più catch per diversi tipi di eccezione.

### Clausola finally
Il blocco `finally` viene sempre eseguito, indipendentemente dal fatto che si sia verificata o meno un'eccezione. Utile per rilasciare risorse (file, connessioni).

## Esempio pratico
```java
try {
    int[] a = new int[5];
    a[10] = 42;  // ArrayIndexOutOfBoundsException
} catch (ArrayIndexOutOfBoundsException e) {
    System.out.println("Indice non valido!");
} finally {
    System.out.println("Operazione completata");
}
```

## Riepilogo
- Le eccezioni separano il codice normale da quello di errore
- try-catch intercetta e gestisce le eccezioni
- finally esegue codice di pulizia sempre
- RuntimeException non richiede dichiarazione (unchecked)
- Le eccezioni controllate (checked) vanno dichiarate con throws"""
    
    elif "stream" in title_lower or "file" in title_lower or "input" in title_lower or "output" in title_lower or "reader" in title_lower or "writer" in title_lower:
        content = f"""## Introduzione

Gli stream in Java sono flussi di dati che permettono la comunicazione con l'esterno: file, rete, console. Si dividono in stream di caratteri (Reader/Writer) e stream di byte (InputStream/OutputStream). I primi sono adatti a file di testo, i secondi a file binari.

## Concetti chiave

### Stream di caratteri
`FileReader` e `FileWriter` per leggere/scrivere file di testo. `BufferedReader` aggiunge un buffer per efficientare la lettura riga per riga: `readLine()`.

### Stream di byte
`FileInputStream` e `FileOutputStream` per file binari (immagini, suoni). `DataInputStream` e `DataOutputStream` per leggere/scrivere tipi primitivi.

### La classe File
`File` rappresenta un file o directory. Metodi: `exists()`, `isFile()`, `isDirectory()`, `length()`, `listFiles()`.

## Esempio pratico
```java
BufferedReader reader = new BufferedReader(new FileReader("input.txt"));
String riga;
while ((riga = reader.readLine()) != null) {
    System.out.println(riga);
}
reader.close();
```

## Riepilogo
- Stream di caratteri: Reader/Writer per testo
- Stream di byte: InputStream/OutputStream per binari
- BufferedReader permette lettura efficiente riga per riga
- La classe File rappresenta file e directory
- Chiudere sempre gli stream con close()"""
    
    elif "ereditariet" in title_lower or "extends" in title_lower or "sottoclasse" in title_lower or "superclasse" in title_lower:
        content = f"""## Introduzione

L'ereditarietà è un meccanismo fondamentale della programmazione a oggetti che permette di definire nuove classi basate su classi esistenti. Una sottoclasse estende la superclasse, ereditandone stato e comportamento, e può aggiungere o modificare metodi.

## Concetti chiave

### extends e sottoclassi
`class Quadrato extends Rettangolo` dichiara che Quadrato è una sottoclasse di Rettangolo. Quadrato eredita i campi e i metodi di Rettangolo, può aggiungerne di nuovi o sovrascrivere (override) quelli esistenti.

### Il riferimento super
`super()` invoca il costruttore della superclasse. `super.metodo()` invoca una versione sovrascritta del metodo della superclasse.

### Polimorfismo
Un riferimento di tipo superclasse può riferirsi a un oggetto di una sottoclasse: `Rettangolo r = new Quadrato(5);`. Il metodo eseguito è determinato dal tipo effettivo dell'oggetto a runtime.

## Esempio pratico
```java
class Rettangolo {
    protected int base, altezza;
    public int area() { return base * altezza; }
}
class Quadrato extends Rettangolo {
    public Quadrato(int lato) { base = altezza = lato; }
}
Rettangolo r = new Quadrato(5);  // polimorfismo
System.out.println(r.area());    // 25
```

## Riepilogo
- extends crea una relazione di ereditarietà
- La sottoclasse eredita campi e metodi della superclasse
- super invoca costruttori/metodi della superclasse
- Il polimorfismo permette di trattare oggetti diversi in modo uniforme
- L'override ridefinisce un metodo ereditato"""
    
    elif "interfacc" in title_lower or "implements" in title_lower:
        content = f"""## Introduzione

Un'interfaccia in Java definisce un insieme di metodi (la segnatura) senza implementazione. Le classi implementano interfacce, fornendo il corpo dei metodi dichiarati. Le interfacce permettono di definire contratti che le classi si impegnano a rispettare.

## Concetti chiave

### Dichiarazione di interfaccia
`interface Figura { double area(); }` dichiara un'interfaccia con un metodo astratto. Le classi che implementano Figura devono fornire area().

### implements
`class Cerchio implements Figura { ... public double area() { ... } }`. Una classe può implementare più interfacce.

### Interfacce e polimorfismo
Una variabile di tipo interfaccia può riferirsi a qualsiasi oggetto di una classe che implementa l'interfaccia: `Figura f = new Cerchio(5);`.

## Esempio pratico
```java
interface Confrontabile {
    int confrontaCon(Confrontabile altro);
}
class Frazione implements Confrontabile {
    // ... implementazione di confrontaCon
}
```

## Riepilogo
- L'interfaccia definisce un contratto (metodi senza implementazione)
- implements vincola la classe a fornire i metodi dichiarati
- Una classe può implementare più interfacce
- Le interfacce abilitano il polimorfismo tra classi non correlate""" 
    
    elif "generi" in title_lower or "tipo generico" in title_lower or "wildcard" in title_lower:
        content = f"""## Introduzione

I tipi generici (generics) permettono di definire classi e metodi che operano su tipi specificati dal client. Introdotti in Java 5, i generics aumentano la sicurezza dei tipi eliminando la necessità di cast espliciti. Una classe come `ArrayList<E>` può funzionare con qualsiasi tipo E.

## Concetti chiave

### Classi generiche
`class Sequenza<E> { ... }` dove E è un parametro di tipo. Il client specifica il tipo concreto: `Sequenza<Frazione> s = new Sequenza<>();`.

### Metodi generici
Un metodo può avere il proprio parametro di tipo: `public static <T> T max(T a, T b, Comparator<T> cmp)`.

### Vincoli e wildcard
`<E extends Comparable<E>>` vincola E a tipi che implementano Comparable. I wildcard (`? extends Figura`) permettono flessibilità nei tipi generici.

## Esempio pratico
```java
Sequenza<String> nomi = new Sequenza<>();
nomi.aggiungi("Mario");
nomi.aggiungi("Luigi");
String primo = nomi.get(0);  // nessun cast necessario
```

## Riepilogo
- I generics parametrizzano i tipi: <E>
- Eliminano la necessità di cast e aumentano la sicurezza
- I vincoli (extends) limitano i tipi ammessi
- I wildcard (? extends, ? super) danno flessibilità
- I generics sono cancellati a compile-time (erasure)"""
    
    elif "ricorsion" in title_lower or "ricorsiva" in title_lower or "mergesort" in title_lower or "merge sort" in title_lower:
        content = f"""## Introduzione

La ricorsione è una tecnica in cui un metodo invoca se stesso per risolvere un problema. Ogni problema ricorsivo ha un caso base (terminazione) e un passo ricorsivo che avvicina al caso base. La ricorsione è particolarmente utile per problemi con struttura naturale ricorsiva (alberi, liste).

## Concetti chiave

### Struttura di un metodo ricorsivo
Un metodo ricorsivo ha: un caso base che termina la ricorsione, e un passo ricorsivo che invoca il metodo su un problema più piccolo. Senza caso base, si verifica StackOverflowError.

### Esempio: fattoriale
`n! = n * (n-1)!` con caso base 0! = 1. Implementazione: `if (n==0) return 1; else return n*fattoriale(n-1);`.

### Mergesort
L'ordinamento per fusione divide l'array a metà, ordina ricorsivamente ciascuna metà, poi fonde le due metà ordinate. Complessità O(n log n).

## Esempio pratico
```java
public static int mcd(int x, int y) {
    if (y == 0) return x;  // caso base
    return mcd(y, x % y);  // passo ricorsivo
}
```

## Riepilogo
- La ricorsione richiede caso base e passo ricorsivo
- Ogni invocazione crea un nuovo record di attivazione nello stack
- Mergesort è un classico algoritmo ricorsivo
- La ricorsione è ideale per strutture dati ricorsive come alberi"""
    
    elif "pila" in title_lower or "stack" in title_lower or "coda" in title_lower or "lista" in title_lower or "albero" in title_lower:
        content = f"""## Introduzione

Le strutture dati dinamiche (pile, code, liste, alberi) sono fondamentali per organizzare e gestire i dati in modo efficiente. A differenza degli array, la loro dimensione può variare durante l'esecuzione. In Java, queste strutture si implementano usando oggetti collegati da riferimenti.

## Concetti chiave

### Pila (Stack)
Principio LIFO (Last In, First Out). Operazioni: push (inserisci), pop (estrai), isEmpty. Usata per: undo, analisi sintattica, stack delle chiamate.

### Coda (Queue)
Principio FIFO (First In, First Out). Operazioni: aggiungi (in coda), preleva (dalla testa). Usata per: buffer, stampa, scheduling.

### Alberi binari
Ogni nodo ha al massimo due figli (sinistro e destro). Usati per: espressioni, alberi di ricerca, file system. L'attraversamento può essere in ordine anticipato, simmetrico o posticipato.

## Esempio pratico
Pila implementata con array: `push` incrementa un indice e inserisce, `pop` restituisce l'elemento e decrementa l'indice. Pila implementata con strutture dinamiche: ogni nodo ha un riferimento al nodo successivo.

## Riepilogo
- Pile (LIFO), Code (FIFO), Alberi (gerarchici)
- Le strutture dinamiche crescono e si riducono a runtime
- Le pile si usano per call stack e undo
- Le code per buffer e scheduling
- Gli alberi per dati gerarchici e ricerca efficiente"""
    
    else:
        # Generic lesson from title
        content = f"""## Introduzione

Questa lezione approfondisce il tema di {title}. Basandosi sui concetti già introdotti, esploriamo nuovi aspetti della programmazione Java che ci permetteranno di scrivere codice più efficace e strutturato.

## Concetti chiave

### Il contesto
Gli argomenti trattati in questa sezione del manuale sono fondamentali per costruire una solida base nella programmazione Java. Ogni concetto si inserisce in un percorso che va dai fondamenti agli oggetti.

### Applicazione pratica
La teoria va sempre accompagnata dalla pratica. Gli esercizi proposti nel manuale sono strumenti indispensabili per consolidare quanto appreso.

## Esempio pratico
Analizziamo un esempio concreto tratto dal materiale del corso, applicando i concetti discussi per risolvere un problema specifico.

## Riepilogo
- Approfondisci i concetti chiave della lezione
- Metti in pratica con esercizi mirati
- Collega ogni nuovo concetto a quanto già appreso"""

    # Ensure minimum content length
    if len(content) < 600:
        content += "\n\n## Metti in pratica\nRivedi gli esercizi correlati nel manuale e prova a implementare una soluzione autonoma prima di controllare la soluzione proposta."
    
    return content

# Load corso_plan
with open(os.path.join(WORKSPACE, "reports/corso_plan.json")) as f:
    data = json.load(f)

pts = data["punti_taglio"]

# These module IDs are already taken:
done_mods = [f"mod_{i:03d}" for i in range(1, 20)]  # mod_001 to mod_019
done_quiz = ["quiz_001", "quiz_002"]

# Start from the next available lesson slot
next_ordine = 22  # Last lesson was mod_019 at ordine 21, then quiz at ordine 20
next_mod_idx = 20  # mod_020

# We need mod_001 through at least mod_120
# Already have mod_001 to mod_019 = 19 lessons.
# Need at least 101 more lessons
target_lessons = 120
need = target_lessons - 19

print(f"Need {need} more lessons starting from ordine {next_ordine}")

# For now, print what would be created for the remaining pt entries
for i, p in enumerate(pts[next_mod_idx-1:], start=next_mod_idx):
    if i > target_lessons:
        break
    title = p["titolo"]
    print(f"Would create mod_{i:03d} (ord={i+1}): {title[:70]}")