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

### Microservizi

Il sistema è composto da diversi microservizi indipendenti, ciascuno responsabile di una specifica area funzionale. Questa suddivisione permette di mantenere separata la logica applicativa, semplificare la manutenzione del progetto e consentire l’integrazione di nuovi servizi nel tempo. La comunicazione tra i vari moduli avviene tramite API e meccanismi di elaborazione asincrona, così da rendere il sistema più flessibile e adatto a gestire carichi variabili.

Il **frontend** fornisce le funzionalità di gestione documentale attraverso un’interfaccia web. Il **backend** espone le API principali del sistema e gestisce autenticazione, autorizzazione, organizzazione dei file, gestione dei permessi e coordinamento delle operazioni.

I metadati dei documenti, degli utenti e delle cartelle vengono salvati all’interno di un **database relazionale**, mentre i file veri e propri sono memorizzati in un sistema di **object storage** separato. Questa separazione consente di migliorare la gestione dei dati e supportare volumi elevati di documenti.

Per le operazioni più costose o asincrone, come l’elaborazione di allegati email, l’estrazione del testo dai documenti e la classificazione automatica tramite agenti AI, il sistema utilizza **worker dedicati** e **code di eventi**. In questo modo le attività di background non bloccano le normali richieste degli utenti e possono essere scalate indipendentemente.

[dettagli riguardo la ricerca e l'elaborazione dei file con Apache Tika]

[immagini dell'architettura]

### Deployment

Per il deployment del sistema è stato scelto **Kubernetes**, una piattaforma di orchestrazione di container che consente di gestire in modo centralizzato i diversi servizi dell’applicazione. Questa soluzione permette di distribuire e coordinare automaticamente i componenti del sistema, semplificando operazioni di aggiornamento, monitoraggio e scalabilità.

L’utilizzo di Kubernetes offre diversi vantaggi, tra cui l’alta disponibilità dei servizi, la possibilità di scalare dinamicamente le componenti più utilizzate e una maggiore affidabilità dell’infrastruttura. Inoltre, la gestione separata dei microservizi consente di aggiornare o sostituire singole componenti senza interrompere il funzionamento dell’intero sistema.

L’approccio containerizzato facilita inoltre la portabilità dell’applicazione tra ambienti diversi, rendendo più semplice il passaggio dallo sviluppo locale a infrastrutture cloud o distribuite.

## Stack tecnologico

### Object storage

Per la gestione dei file è stato adottato un sistema di object storage, con l’obiettivo di separare i contenuti binari (documenti e allegati) dai metadati gestiti nel database relazionale. Questa scelta consente una migliore scalabilità e una gestione più efficiente di grandi volumi di dati non strutturati.

Sono state considerate diverse soluzioni: storage S3 compatibili gestiti, MinIO, SeaweedFS, Garage e Ceph. Le soluzioni S3 gestite rappresentano lo standard industriale in termini di affidabilità e scalabilità, ma introducono dipendenza da provider esterni e costi variabili. MinIO offre una soluzione open source compatibile con S3, semplice da integrare ma il progetto non è più mantenuto. Ceph è una piattaforma molto completa e robusta, adatta a contesti enterprise, ma caratterizzata da elevata complessità operativa e costi infrastrutturali significativi. Garage, infine, è una soluzione più recente e orientata alla resilienza distribuita, ma con un ecosistema ancora meno maturo.

È stato scelto **SeaweedFS** per il progetto grazie al buon equilibrio tra semplicità, prestazioni e capacità di scalare orizzontalmente, mantenendo al tempo stesso un’integrazione diretta con ambienti containerizzati e una gestione più leggera rispetto ad alternative più complesse.

Un ulteriore vantaggio dell’approccio adottato è l’utilizzo del protocollo S3 come standard di interoperabilità. Questo consente di mantenere il sistema indipendente dall’implementazione specifica dello storage e rende possibile, in futuro, migrare verso soluzioni alternative (come MinIO, Ceph o storage S3 gestiti) senza modifiche sostanziali all’architettura applicativa.

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

Nel sistema, OpenSearch viene alimentato dai contenuti estratti tramite Apache Tika. I documenti vengono elaborati da worker dedicati che estraggono il testo, generano eventuali embeddings e aggiornano l’indice di ricerca. Questo approccio asincrono consente di mantenere separate le operazioni di upload dalla fase di indicizzazione, migliorando la scalabilità e le prestazioni complessive della piattaforma.

Infine, l’adozione di OpenSearch permette di estendere facilmente il sistema con funzionalità future legate all’intelligenza artificiale, come sistemi di recommendation, ricerca semantica avanzata e integrazione con pipeline RAG basate su modelli linguistici.

### Classificazione automatica

Il sistema include una funzionalità di classificazione automatica dei documenti con l’obiettivo di semplificare l’organizzazione dei file caricati dagli utenti e ridurre le operazioni manuali di gestione delle cartelle.

La pipeline di elaborazione inizia con **Apache Tika**, che estrae il contenuto testuale e i metadati dai documenti caricati nel sistema. Il testo ottenuto viene quindi utilizzato come input per un agente AI incaricato di determinare la categoria o la directory più appropriata in cui collocare il documento.

L’agente è stato sviluppato utilizzando **Atomic Agents**, un framework che consente di costruire agenti modulari e integrabili con strumenti esterni. Per interagire con il sistema documentale, l’agente utilizza un server **MCP** (Model Context Protocol) che espone una serie di tool dedicati all’accesso controllato alle informazioni del DMS, come la visualizzazione delle directory disponibili e i file che contengono.

Attraverso questi strumenti l’agente può analizzare la struttura esistente del sistema documentale e confrontare il contenuto del nuovo file con i documenti già archiviati. In questo modo la classificazione non si basa solamente sul nome del file o su regole statiche, ma sul contenuto semantico del documento e sul contesto organizzativo già presente nel sistema.

L’intero processo viene eseguito in modo asincrono tramite worker dedicati e code di elaborazione, così da non impattare sulle operazioni di upload effettuate dagli utenti. Questa architettura consente inoltre di estendere facilmente il comportamento dell’agente introducendo nuovi strumenti MCP o nuove strategie di classificazione senza modificare le componenti principali del sistema.

### Caricamento automatico

Il sistema integra una funzionalità di acquisizione automatica dei documenti tramite email, con l’obiettivo di semplificare ulteriormente il caricamento dei file e automatizzare il processo di archiviazione documentale.

Per ogni utente è possibile configurare uno o più account email associati al sistema. Un componente software dedicato effettua periodicamente il collegamento ai server di posta tramite protocollo **IMAP**, verificando la presenza di nuovi messaggi ricevuti e individuando eventuali allegati.

Gli allegati vengono quindi estratti dalle email e salvati nel sistema di object storage, mantenendo separata la gestione dei file dai metadati applicativi. Contestualmente vengono creati gli opportuni riferimenti nel database, così da integrare i documenti all’interno del DMS come normali file caricati dagli utenti.

Successivamente, i documenti acquisiti vengono inseriti nella pipeline di elaborazione descritta nei capitoli precedenti. In particolare, Apache Tika viene utilizzato per estrarre automaticamente il contenuto testuale degli allegati, indipendentemente dal formato del file. Il testo ottenuto può quindi essere utilizzato sia per l’indicizzazione nel motore di ricerca sia per le funzionalità di classificazione automatica tramite agente AI.

Questo approccio consente di trasformare la posta elettronica in un canale di acquisizione documentale completamente integrato con il sistema, riducendo le operazioni manuali richieste agli utenti e migliorando l’automazione dell’intero flusso di gestione dei documenti.

L’elaborazione viene eseguita in modo asincrono tramite componenti separati e code di elaborazione, così da mantenere indipendenti le operazioni di polling delle email, archiviazione dei file, estrazione del testo e classificazione automatica. Questa suddivisione permette di scalare separatamente le diverse componenti del sistema e garantire una maggiore affidabilità anche in presenza di elevati volumi di documenti o allegati email.

## Test di carico
