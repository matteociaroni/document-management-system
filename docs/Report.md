# Document Management System

## Abstract

Il progetto consiste nello sviluppo di un sistema distribuito per la gestione documentale, progettato per consentire agli utenti di archiviare, organizzare, condividere ed elaborare documenti digitali in modo sicuro e scalabile. La piattaforma mette a disposizione funzionalità per la gestione di file e cartelle, il controllo degli accessi e la condivisione dei contenuti tra utenti.

L’architettura del sistema segue un approccio modulare, in modo da permettere l’integrazione di servizi aggiuntivi e la scalabilità delle diverse componenti. Il sistema supporta sia il caricamento manuale dei documenti sia l’acquisizione automatica di allegati provenienti da caselle email collegate dagli utenti.

Una parte significativa del progetto riguarda l’elaborazione automatica dei documenti. I file caricati possono essere analizzati per abilitare funzionalità di ricerca avanzata e classificazione automatica. Il sistema è inoltre progettato per integrare agenti basati su intelligenza artificiale, in grado di supportare l’organizzazione dei documenti e l’automazione di alcune operazioni, come il caricamento automatico degli allegati ricevuti via email.

L’obiettivo del progetto è realizzare una piattaforma moderna ed estendibile, capace di combinare gestione documentale, automazione e strumenti di intelligenza artificiale in un’unica soluzione integrata.

## Analisi requisiti

Dal punto di vista funzionale, il sistema deve permettere agli utenti di caricare, organizzare e gestire documenti attraverso una struttura basata su cartelle. Devono inoltre essere supportate operazioni di condivisione e gestione dei permessi, così da consentire l’accesso controllato ai contenuti. Un ulteriore requisito riguarda l’integrazione con caselle email esterne, in modo da acquisire automaticamente allegati e documenti.

Particolare attenzione è stata dedicata alle funzionalità di ricerca e automazione. Il sistema deve essere in grado di estrarre contenuto testuale dai documenti caricati, consentendo ricerche avanzate e l’utilizzo di strumenti basati su intelligenza artificiale per la classificazione automatica e l’organizzazione dei file.

Nella progettazione dell’architettura del sistema, è stato adottando un approccio a microservizi per separare le diverse responsabilità applicative e facilitare l’evoluzione della piattaforma. Questa scelta consente di scalare in modo indipendente i vari componenti del sistema, migliorando flessibilità e affidabilità. Inoltre, il sistema è stato progettato considerando scenari multi-tenant, così da permettere la gestione isolata dei dati e delle risorse appartenenti a utenti o organizzazioni differenti.

## Architettura del sistema

Il sistema è composto da diversi **microservizi** indipendenti, ciascuno responsabile di una specifica area funzionale. Questa suddivisione permette di mantenere separata la logica applicativa, semplificare la manutenzione del progetto e consentire l’integrazione di nuovi servizi nel tempo. La comunicazione tra i vari moduli avviene tramite API e meccanismi di elaborazione asincrona, così da rendere il sistema più flessibile e adatto a gestire carichi variabili.

Il **frontend** fornisce le funzionalità di gestione documentale attraverso un’interfaccia web. Il **backend** espone le API principali del sistema e gestisce autenticazione, autorizzazione, organizzazione dei file, gestione dei permessi e coordinamento delle operazioni.

I metadati dei documenti, degli utenti e delle cartelle vengono salvati all’interno di un **database relazionale**, mentre i file veri e propri sono memorizzati in un sistema di **object storage** separato. Questa separazione consente di migliorare la gestione dei dati e supportare volumi elevati di documenti.

Per le operazioni più costose o asincrone, come l’elaborazione di allegati email, l’estrazione del testo dai documenti, l'indicizzazione per la ricerca e la classificazione automatica tramite agenti AI, il sistema utilizza **worker dedicati** e **code di eventi**. In questo modo le attività di background non bloccano le normali richieste degli utenti e possono essere scalate indipendentemente.

[immagini dell'architettura]

## Stack tecnologico

### Object storage

Per la gestione dei documenti è stato adottato un sistema di object storage, separando i contenuti binari dai metadati gestiti nel database relazionale. Questo approccio consente di migliorare la scalabilità del sistema e di gestire in modo più efficiente grandi quantità di file, evitando di memorizzare documenti direttamente all’interno del database.

Durante la progettazione sono state considerate diverse tipologie di storage, tra cui filesystem tradizionali che però, nonpsytante risultino semplici da utilizzare in ambienti limitati, presentano difficoltà nella gestione della scalabilità, della replica e dell’alta disponibilità in contesti distribuiti.

Per questi motivi è stato scelto di adottare uno storage compatibile con il protocollo **S3**, oggi considerato uno standard de facto per l’object storage. Questo modello offre diversi vantaggi: elevata scalabilità, semplicità di integrazione applicativa, gestione efficiente di file di grandi dimensioni e disponibilità di librerie e strumenti compatibili in praticamente tutti gli ecosistemi software moderni.

L’utilizzo di API compatibili S3 consente inoltre di mantenere il sistema indipendente dal provider o dall’implementazione specifica dello storage. L’applicazione interagisce infatti tramite le API standard del protocollo, rendendo possibile migrare in futuro verso soluzioni differenti (self-hosted o gestite) senza modifiche significative all’architettura applicativa.

Questa scelta permette quindi di ottenere un buon compromesso tra semplicità di integrazione, portabilità e possibilità di evoluzione futura dell’infrastruttura.

### Database relazionale

Per la gestione dei dati strutturati del sistema è stato adottato un database relazionale, responsabile della memorizzazione di tutte le informazioni legate a utenti, documenti, cartelle, permessi ed eventi applicativi, garantendo consistenza e integrità dei dati.

Tra le alternative considerate rientrano MySQL e PostgreSQL. MySQL rappresenta una soluzione molto diffusa e stabile, con buone prestazioni nelle operazioni di lettura, ma con funzionalità più limitate nella gestione di dati complessi e nell’estensibilità. PostgreSQL, invece, offre un modello più avanzato, supportando tipi di dato complessi, query più espressive e funzionalità avanzate come JSONB, che risultano particolarmente utili in un sistema ibrido tra dati strutturati e semi-strutturati.

La scelta è ricaduta su **PostgreSQL** principalmente per la sua robustezza, affidabilità e capacità di gestire in modo efficiente relazioni complesse tra entità come utenti, documenti e permessi. Inoltre, il supporto a transazioni ACID garantisce la coerenza dei dati anche in scenari concorrenti e distribuiti.

Un ulteriore vantaggio è la possibilità di estendere il database con funzionalità avanzate, come la full-text search e l’integrazione con dati JSON, rendendolo adatto non solo alla gestione dei metadati, ma anche a funzionalità come la ricerca.

Infine, l’adozione di PostgreSQL si inserisce coerentemente in un’architettura modulare e containerizzata, permettendo una facile integrazione con sistemi di orchestrazione e garantendo la possibilità di scalare o migrare l’infrastruttura in modo progressivo senza impatti significativi sull’applicazione.

### Backend

Il backend del sistema è stato sviluppato utilizzando **FastAPI**, un framework moderno per la costruzione di API ad alte prestazioni basato su **Python**. Il backend rappresenta il nucleo logico dell’applicazione e si occupa della gestione delle richieste provenienti dal frontend, dell’autenticazione degli utenti, della gestione dei documenti e del coordinamento delle diverse componenti del sistema.

Tra le alternative considerate rientrano framework come Django e Flask. Django offre una soluzione completa, con molte funzionalità già integrate, ma risulta meno flessibile in architetture fortemente modulari e basate su microservizi. Flask, al contrario, è molto leggero e flessibile, ma richiede l’integrazione manuale di molte componenti per gestire funzionalità avanzate come validazione dei dati, documentazione API e gestione asincrona.

FastAPI è stato scelto per il progetto grazie al suo equilibrio tra semplicità, prestazioni e modernità. Supporta nativamente la programmazione asincrona, risultando particolarmente adatto a gestire operazioni I/O intensive come accesso allo storage, comunicazione con servizi esterni e gestione di code di elaborazione. Inoltre, la validazione automatica dei dati tramite Pydantic e la generazione automatica della documentazione delle API semplificano lo sviluppo e migliorano la manutenibilità del sistema.

Un ulteriore vantaggio è la sua naturale compatibilità con architetture a microservizi, che consente di separare chiaramente le responsabilità applicative e scalare in modo indipendente le diverse componenti del backend. Questo si integra perfettamente con l’approccio containerizzato e orchestrato del sistema, rendendo il backend facilmente distribuibile in ambienti Kubernetes o simili.

### Frontend

Il frontend del sistema è stato sviluppato utilizzando **React**, una libreria JavaScript ampiamente utilizzata per la costruzione di interfacce utente dinamiche e component-based. L’interfaccia rappresenta il punto di accesso principale per l’utente e consente la gestione completa dei documenti, delle cartelle e delle funzionalità di ricerca e condivisione.

Tra le alternative considerate rientrano framework come Angular e Vue.js. Angular offre una soluzione strutturata e completa, adatta a progetti enterprise, ma con una maggiore complessità iniziale e una curva di apprendimento più ripida. Vue.js, invece, è più leggero e semplice da integrare, ma meno diffuso in contesti di grandi applicazioni e con un ecosistema leggermente più ridotto rispetto a React.

La scelta di React è stata motivata dalla sua flessibilità e dalla forte diffusione nell’ambito dello sviluppo web moderno. L’approccio basato su componenti riutilizzabili consente di costruire un’interfaccia modulare e facilmente manutenibile, facilitando l’evoluzione del sistema nel tempo.

Un ulteriore vantaggio è l’ampio ecosistema di librerie e strumenti disponibili, che permette di integrare facilmente funzionalità avanzate come gestione dello stato, routing e comunicazione con le API backend. Questo rende React particolarmente adatto a un’applicazione complessa e in continua evoluzione come un sistema di gestione documentale.

Infine, il frontend è stato progettato per comunicare esclusivamente tramite API REST con il backend, garantendo una netta separazione tra logica di presentazione e logica applicativa. Questo approccio favorisce la scalabilità e consente in futuro di sostituire o estendere l’interfaccia utente senza modificare la parte server.

### Estrazione del testo dai file

Per l’elaborazione automatica dei documenti è stato utilizzato **Apache Tika**, un framework open source progettato per l’estrazione di testo e metadati da numerosi formati di file, tra cui PDF, documenti Office, file di testo e immagini contenenti testo.

L’utilizzo di Apache Tika consente al sistema di ottenere una rappresentazione testuale uniforme dei documenti caricati dagli utenti o acquisiti automaticamente tramite allegati email. Questo passaggio è fondamentale poiché i file binari non possono essere elaborati direttamente dai servizi di ricerca o dagli agenti AI.

Tra le alternative considerate rientrano librerie specifiche per singoli formati, come parser dedicati ai PDF o ai documenti Office. Tuttavia, queste soluzioni avrebbero richiesto l’integrazione e la manutenzione di strumenti differenti per ogni tipologia di file supportata. Apache Tika offre invece un’interfaccia unificata e indipendente dal formato del documento, semplificando notevolmente la pipeline di elaborazione.

Nel progetto, Tika viene utilizzato principalmente per due scopi. Il primo riguarda la ricerca documentale: il testo estratto dai file viene indicizzato così da consentire ricerche full-text e semantiche sui contenuti dei documenti. Il secondo riguarda l’elaborazione automatica tramite agenti AI: il contenuto estratto viene utilizzato per analizzare il significato dei documenti e supportare operazioni di classificazione e organizzazione automatica all’interno del sistema.

### Ricerca dei file

Per implementare le funzionalità di ricerca avanzata è stato adottato **OpenSearch**, un motore di ricerca progettato per l’indicizzazione e l’interrogazione efficiente di grandi quantità di dati testuali.

L’utilizzo di un motore di ricerca dedicato si è reso necessario poiché il database relazionale utilizzato dal sistema contiene principalmente metadati e non è ottimizzato per eseguire ricerche complesse sul contenuto completo dei documenti. Attraverso OpenSearch è invece possibile indicizzare il testo estratto dai file e fornire ricerche rapide anche su dataset di grandi dimensioni.

Tra le alternative considerate rientrano Elasticsearch e la full-text search nativa di PostgreSQL. La ricerca full-text di PostgreSQL rappresenta una soluzione semplice da integrare e sufficiente per casi limitati, ma meno adatta a gestire funzionalità avanzate e carichi elevati su grandi quantità di documenti. Elasticsearch costituisce invece il principale riferimento del settore, ma OpenSearch è stato preferito in quanto completamente open source e compatibile con gran parte dell’ecosistema Elasticsearch.

OpenSearch offre inoltre funzionalità particolarmente utili per il progetto, come il supporto alla ricerca full-text, filtri avanzati, ranking dei risultati e ricerca vettoriale tramite embeddings. Questo consente non solo di effettuare ricerche basate su parole chiave, ma anche ricerche semantiche in grado di individuare documenti concettualmente simili alle query dell’utente.

Per supportare la ricerca semantica, il sistema genera embeddings a partire dal testo estratto dai documenti utilizzando il modello **paraphrase-multilingual-MiniLM-L12-v2**, scelto per il buon compromesso tra qualità dei risultati, supporto multilingua e ridotto consumo di risorse computazionali. Gli embeddings prodotti vengono salvati in OpenSearch e utilizzati per confrontare semanticamente query e documenti.

Nel sistema, OpenSearch viene alimentato dai contenuti estratti tramite Apache Tika. I documenti vengono elaborati da worker dedicati che estraggono il testo, generano gli embeddings e aggiornano l’indice di ricerca. Questo approccio asincrono consente di mantenere separate le operazioni di upload dalla fase di indicizzazione, migliorando la scalabilità e le prestazioni complessive della piattaforma.

Infine, l’adozione di OpenSearch permette di estendere facilmente il sistema con funzionalità future legate all’intelligenza artificiale, come sistemi di recommendation, ricerca semantica avanzata e integrazione con pipeline RAG basate su modelli linguistici.

### Classificazione automatica

Il sistema include una funzionalità di classificazione automatica dei documenti con l’obiettivo di semplificare l’organizzazione dei file caricati dagli utenti e ridurre le operazioni manuali di gestione delle cartelle.

La pipeline di elaborazione inizia con **Apache Tika**, che estrae il contenuto testuale e i metadati dai documenti caricati nel sistema. Il testo ottenuto viene quindi utilizzato come input per un agente AI incaricato di determinare la categoria o la directory più appropriata in cui collocare il documento.

Il testo del file che viene inviato all'LLM viene ridotto ai solo primi 2000 caratteri, in modo da risparmiare token e tempo di elaborazione mantenendo comunque un contesto sufficiente a permettere una corretta classificazione del file.

L’agente è stato sviluppato utilizzando **Atomic Agents**, un framework che consente di costruire agenti modulari e integrabili con strumenti esterni. Per interagire con il sistema documentale, l’agente utilizza un server **MCP** (Model Context Protocol) che espone una serie di tool dedicati all’accesso controllato alle informazioni del DMS, in partiolare:

- la visualizzazione delle directory disponibili
- informazioni (nome, gerarchia) di una directory
- i file che contiene una directory


Attraverso questi strumenti l’agente può analizzare la struttura esistente del sistema documentale e confrontare il contenuto del nuovo file con i documenti già archiviati. In questo modo la classificazione non si basa solamente sul nome del file o su regole statiche, ma sul contenuto semantico del documento e sul contesto organizzativo già presente nel sistema.

L’intero processo viene eseguito in modo asincrono tramite worker dedicati e code di elaborazione, così da non impattare sulle operazioni di upload effettuate dagli utenti. Questa architettura consente inoltre di estendere facilmente il comportamento dell’agente introducendo nuovi strumenti MCP o nuove strategie di classificazione senza modificare le componenti principali del sistema.

### Caricamento automatico

Il sistema integra una funzionalità di acquisizione automatica dei documenti tramite email, con l’obiettivo di semplificare ulteriormente il caricamento dei file e automatizzare il processo di archiviazione documentale.

Per ogni utente è possibile configurare uno o più account email associati al sistema. Un componente software dedicato effettua periodicamente il collegamento ai server di posta tramite protocollo **IMAP**, verificando la presenza di nuovi messaggi ricevuti e individuando eventuali allegati.

Gli allegati vengono quindi estratti dalle email e salvati nel sistema di object storage; contestualmente vengono creati gli opportuni riferimenti nel database, così da integrare i documenti all’interno del DMS come normali file caricati dagli utenti.

Successivamente, i documenti acquisiti vengono inseriti nella pipeline di elaborazione descritta nei capitoli precedenti. In particolare, Apache Tika viene utilizzato per estrarre automaticamente il contenuto testuale degli allegati, indipendentemente dal formato del file. Il testo ottenuto può quindi essere utilizzato sia per l’indicizzazione nel motore di ricerca sia per le funzionalità di classificazione automatica tramite agente AI.

Questo approccio consente di trasformare la posta elettronica in un canale di acquisizione documentale completamente integrato con il sistema, riducendo le operazioni manuali richieste agli utenti e migliorando l’automazione dell’intero flusso di gestione dei documenti.

L’elaborazione viene eseguita in modo asincrono tramite componenti separati e code di elaborazione, così da mantenere indipendenti le operazioni di polling delle email, archiviazione dei file, estrazione del testo e classificazione automatica. Questa suddivisione permette di scalare separatamente le diverse componenti del sistema e garantire una maggiore affidabilità anche in presenza di elevati volumi di documenti o allegati email.

## Deployment e infrarastruttura 

Per il deployment della piattaforma è stato scelto **Google Cloud Platform** come provider cloud, principalmente per la disponibilità di servizi gestiti, l’integrazione con ambienti containerizzati e la semplicità di scalabilità dell’infrastruttura.

### Storage
Una delle principali decisioni architetturali ha riguardato la gestione dei componenti stateful del sistema. Servizi come il database relazionale e l’object storage richiedono infatti meccanismi complessi di replica, persistenza e gestione della consistenza dei dati, soprattutto in ambienti distribuiti e ad alta disponibilità. Per ridurre la complessità operativa e migliorare l’affidabilità complessiva della piattaforma, è stato quindi scelto di utilizzare **servizi gestiti** per PostgreSQL e per lo storage compatibile S3 in modo da delegare al provider attività critiche come:

- replica dei dati;
- backup automatici;
- failover;
- aggiornamenti;
- scalabilità dello storage.

Questo approccio permette di concentrarsi maggiormente sullo sviluppo applicativo evitando la gestione diretta di cluster stateful complessi, che avrebbero introdotto costi operativi significativamente maggiori.

### Kubernetes

Per quanto riguarda gli altri componenti della piattaforma, la maggior parte dei servizi è stata progettata secondo un’architettura stateless, in modo che i microservizi possano essere replicati orizzontalmente senza necessità di sincronizzazione dello stato interno.

Per orchestrare questi servizi è stato adottato Kubernetes, eseguito su tre macchine virtuali distribuite su GCP. In particolare, è stata scelta una distribuzione leggera del cluster basata su **k3s**, una versione semplificata di Kubernetes progettata per ambienti con risorse ridotte e per deployment edge o su infrastrutture non particolarmente complesse. L’utilizzo di k3s consente di ridurre l’overhead operativo del control plane, semplificando l’installazione e la manutenzione del cluster, pur mantenendo piena compatibilità con le API Kubernetes standard.

Questa scelta è stata effettuata in ottica di semplicità iniziale e rapidità di gestione dell’infrastruttura. Tuttavia, l’architettura rimane pienamente compatibile con una futura evoluzione verso un cluster Kubernetes “full” più robusto e scalabile. In caso di crescita significativa del sistema, è infatti possibile migrare con relativa facilità verso una soluzione Kubernetes standard o gestita, senza modifiche sostanziali ai deployment o all’architettura dei microservizi.

Kubernetes consente di automatizzare il deployment, il bilanciamento del carico, il riavvio automatico dei container e la scalabilità orizzontale dei vari componenti applicativi. L’adozione di k3s si inserisce quindi in una scelta di pragmatismo, mantenendo al tempo stesso la possibilità di evoluzione verso infrastrutture più complesse.

La scelta di utilizzare Kubernetes permette inoltre di mantenere un’infrastruttura modulare ed estendibile, semplificando l’aggiunta di nuovi microservizi e garantendo una gestione uniforme dell’intero ambiente applicativo.

### Agente di monitoraggio

La piattaforma include un sistema di monitoraggio automatico basato su un agente AI, progettato per semplificare l’individuazione e l’analisi dei problemi applicativi all’interno del cluster Kubernetes.

Il sistema si basa su un server MCP che espone in modo controllato alcune API di Kubernetes, permettendo all’agente di interrogare il cluster ed eseguire operazioni di osservabilità, come la lettura dei log dei pod e lo stato dei servizi in esecuzione.

Quando vengono rilevati errori o anomalie nei container applicativi, l’agente analizza automaticamente i log ottenuti tramite il server MCP e tenta di identificare la possibile causa del problema e una potenziale soluzione o azione correttiva.

Al termine dell’analisi, il sistema invia una notifica tramite Telegram contenente un riepilogo del problema, il log rilevante e le indicazioni generate dall’agente AI. Questo approccio consente di ridurre i tempi di individuazione dei malfunzionamenti e semplifica le attività di monitoraggio operativo dell’infrastruttura.

L’utilizzo di MCP permette inoltre di mantenere separata la logica dell’agente dall’accesso diretto al cluster Kubernetes, introducendo un ulteriore livello di controllo e modularità nell’architettura del sistema

## Test di carico

Per valutare le prestazioni del sistema è stato utilizzato Locust, uno strumento di load testing che consente di simulare il comportamento simultaneo di più utenti reali attraverso scenari di utilizzo definiti a livello applicativo.

Il test è stato progettato per riprodurre le principali operazioni eseguite dagli utenti sulla piattaforma, tra cui autenticazione, gestione delle cartelle, visualizzazione dei documenti e caricamento dei file tramite presigned URL. Ogni utente simulato esegue una sequenza di operazioni realistiche, alternando richieste di lettura e scrittura con tempi di attesa variabili, in modo da rappresentare un utilizzo vicino a quello reale del sistema.

L’esecuzione dei test è stata effettuata su un’istanza del backend distribuita su Kubernetes con 5 repliche attive, al fine di verificare la capacità del sistema di scalare orizzontalmente sotto carico.

### Risultati 

I risultati ottenuti mostrano che l’architettura è in grado di supportare circa 200 utenti concorrenti, equivalenti a circa 100 richieste al secondo in condizioni di carico stabile. La latenza mediana delle richieste si attesta intorno ai 200 ms, mentre il 95° percentile rimane inferiore a circa 1 secondo.

[immagine Locust]

Oltre questa soglia si osserva un degrado delle prestazioni non dovuto al layer applicativo, che continua a scalare correttamente grazie alla replicazione dei pod, ma al numero massimo di connessioni disponibili verso il database relazionale. Il servizio di database gestito Google CloudSQL impone infatti un limite di circa 100 connessioni simultanee, che viene raggiunto in condizioni di carico elevato, diventando il principale collo di bottiglia del sistema.

Questi risultati confermano che la separazione in microservizi e l’utilizzo di un backend stateless, replicabile orizzontalmente su Kubernetes, consente di mantenere buone prestazioni anche in scenari di carico significativo, mentre le limitazioni residue sono legate principalmente ai vincoli del livello di persistenza gestito esternamente.

## Modello di business

### Analisi dei costi

#### Costi fissi

I costi fissi sono legati all’infrastruttura sempre attiva necessaria per il funzionamento della piattaforma. In particolare, rientrano in questa categoria il database relazionale e le macchine virtuali utilizzate per l’esecuzione dei servizi applicativi.

Il database **PostgreSQL** è stato adottato in versione gestita per ridurre la complessità operativa legata alla gestione di replica, backup e alta disponibilità. Questo comporta un costo fisso mensile di 100€.

A questi si aggiunge il costo delle **macchine virtuali** utilizzate per eseguire il cluster Kubernetes e i servizi applicativi. L’infrastruttura è composta da tre VM, per un costo complessivo di 180€ al mese.

Nel complesso, i costi fissi dell’infrastruttura si attestano quindi a 280€ mensili.

#### Costi variabili

I costi variabili sono costituiti dall’**object storage** che è infatti il componente che cresce proporzionalmente alla quantità di dati caricati nel sistema. Il suo costo ammonta a 20€ per TB al mese.

### Modello di pricing

A partire dalla struttura dei costi analizzata, è stato definito un modello di pricing pensato per un contesto B2B, con l’obiettivo di mantenere semplicità commerciale e prevedibilità dei costi per le aziende clienti.

Il modello adottato si basa su un piano unico, che include sia l’utilizzo della piattaforma sia una quota predefinita di risorse.

In particolare, il piano prevede un costo fisso di **100€ al mese per azienda**, che include:

- fino a 5 utenti attivi;
- 1 TB di storage;
- accesso completo alle funzionalità della piattaforma, incluse ricerca avanzata, classificazione automatica dei documenti e automazione dei processi di ingestione.

L’eventuale utilizzo eccedente lo storage incluso può essere monetizzato tramite una tariffazione aggiuntiva proporzionale.

La scelta di un piano semplice e tutto incluso per una soglia base è motivata dalla necessità di ridurre la complessità decisionale in fase di adozione. In ambito B2B, soprattutto per piccole e medie imprese, la chiarezza del pricing rappresenta un fattore determinante nella fase di valutazione di nuovi strumenti software.

Inoltre, il modello proposto consente di coprire i costi fissi dell’infrastruttura già con un numero limitato di clienti, garantendo sostenibilità economica anche nelle prime fasi di crescita della piattaforma.
