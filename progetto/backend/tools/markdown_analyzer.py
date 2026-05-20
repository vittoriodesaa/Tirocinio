import re
from collections import Counter
from typing import List, Dict, Any, Tuple

# Set di stop words (italiano + inglese) prese dal tuo HTML
STOP_WORDS = set("il lo la le i gli un una uno dei del della dello di a ad al alle ai agli in nel nella nello nei negli su sul sulla sullo sui sugli con per tra fra da che chi cui non si mi ti ci vi ne e o ma se come quando dove anche già più meno molto poco ogni questo questa questi queste quello quella quelli quelle ho hai ha abbiamo avete hanno sono sei siamo siete the an and or but on at to for of with is are was were be been it this that you he she we they my your his her our their from by as if so do does did not no have has had will would could should may might can".split())

class MarkdownAnalyzer:
    """
    Analizzatore strutturale e statistico per documenti Markdown.
    Traduzione nativa Python del tool MD Analyzer.
    """

    @staticmethod
    def strip_markdown(text: str) -> str:
        """Rimuove la sintassi Markdown per ottenere il testo puro."""
        text = re.sub(r'```[\s\S]*?```', ' ', text) # Blocchi di codice
        text = re.sub(r'`[^`]+`', ' ', text) # Codice inline
        text = re.sub(r'!\[.*?\]\(.*?\)', ' ', text) # Immagini
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text) # Link (mantiene il testo)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE) # Titoli
        text = re.sub(r'^[-*_]{3,}$', ' ', text, flags=re.MULTILINE) # Separatori
        text = re.sub(r'[*_~`#>|]', ' ', text) # Caratteri speciali residui
        text = re.sub(r'\s+', ' ', text) # Spazi multipli
        return text.strip()

    @staticmethod
    def get_words(text: str) -> List[str]:
        """Estrae una lista di parole pulite dal testo."""
        plain = MarkdownAnalyzer.strip_markdown(text)
        return [w for w in re.split(r'\s+', plain) if w]

    @staticmethod
    def top_frequencies(words: List[str], n: int = 10) -> List[Tuple[str, int]]:
        """Restituisce le N parole più frequenti escludendo le stop words."""
        cleaned_words = []
        for w in words:
            # Pulisce la parola tenendo solo lettere e numeri
            k = re.sub(r'[^a-zàèéìòù0-9]', '', w.lower())
            if len(k) > 2 and k not in STOP_WORDS:
                cleaned_words.append(k)
        
        counter = Counter(cleaned_words)
        return counter.most_common(n)

    @staticmethod
    def calc_stats(raw_md: str) -> Dict[str, Any]:
        """Calcola le statistiche generali di un blocco Markdown."""
        words = MarkdownAnalyzer.get_words(raw_md)
        plain = MarkdownAnalyzer.strip_markdown(raw_md)
        lines = raw_md.split('\n')
        
        sentences = len(re.findall(r'[^.!?]+[.!?]+', plain))
        
        return {
            "words": len(words),
            "chars": len(raw_md),
            "chars_no_spaces": len(re.sub(r'\s', '', raw_md)),
            "lines": len(lines),
            "empty_lines": len([l for l in lines if not l.strip()]),
            "sentences": sentences,
            "code_blocks": len(re.findall(r'```[\s\S]*?```', raw_md)),
            "links": len(re.findall(r'\[([^\]]+)\]\([^)]+\)', raw_md)),
            "images": len(re.findall(r'!\[.*?\]\(.*?\)', raw_md)),
            "bold": len(re.findall(r'\*\*[^*]+\*\*', raw_md)),
            "lists": len([l for l in lines if re.match(r'^[-*+]\s|^\d+\.\s', l.strip())]),
            "top_words": MarkdownAnalyzer.top_frequencies(words, 5)
        }

    @staticmethod
    def extract_sections(raw_md: str, max_level: int = 2) -> List[Dict[str, Any]]:
        """
        Suddivide il documento in sezioni basate sui titoli Markdown (es. H2).
        Se max_level=2, splitta per H1 e H2. Traccia l'impaginazione.
        """
        lines = raw_md.split('\n')
        # Regex dinamica in base al livello massimo richiesto
        pattern = re.compile(rf'^(#{{1,{max_level}}})\s+(.+)')
        
        sections = []
        current_section = None
        current_page = 1  # 1. Contatore iniziale
        
        for line in lines:
            # 2. Rilevatore di pagina (cerca i trattini di PyMuPDF)
            if re.match(r'^[-*_]{3,}$', line.strip()):
                current_page += 1
                
            match = pattern.match(line)
            if match:
                if current_section:
                    # 4. Formattazione spaziale con il trattino e chiusura della sezione precedente
                    current_section['page_range'] = f"{current_section['start_page']}-{current_page}"
                    current_section['raw_content'] = '\n'.join(current_section['lines'])
                    del current_section['lines']
                    sections.append(current_section)
                
                # 3. Inizio del Macro-Argomento
                current_section = {
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                    "start_page": current_page,
                    "lines": [line]
                }
            else:
                if current_section:
                    current_section['lines'].append(line)
                elif line.strip():
                    # Testo prima del primissimo titolo (Introduzione implicita)
                    if not current_section:
                        current_section = {
                            "level": 0,
                            "title": "Introduzione",
                            "start_page": current_page,
                            "lines": []
                        }
                    current_section['lines'].append(line)

        # Aggiunge l'ultima sezione rimasta in canna
        if current_section:
            # 4. Formattazione spaziale con il trattino e chiusura dell'ultima sezione
            current_section['page_range'] = f"{current_section['start_page']}-{current_page}"
            current_section['raw_content'] = '\n'.join(current_section['lines'])
            del current_section['lines']
            sections.append(current_section)

        # Calcola le statistiche per ogni sezione trovata
        for sec in sections:
            sec['stats'] = MarkdownAnalyzer.calc_stats(sec['raw_content'])

        return sections

    @staticmethod
    def analyze(raw_md: str, section_level: int = 2) -> Dict[str, Any]:
        """
        Metodo principale. Analizza l'intero documento e lo divide in sezioni.
        Restituisce un dizionario pronto per essere usato dalla tua pipeline logica.
        """
        global_stats = MarkdownAnalyzer.calc_stats(raw_md)
        sections = MarkdownAnalyzer.extract_sections(raw_md, max_level=section_level)
        
        # Determina la tipologia di documento (Strutturato vs Piatto)
        is_flat = len(sections) <= 1
        
        return {
            "is_flat": is_flat,
            "section_count": len(sections),
            "global_stats": global_stats,
            "sections": sections
        }