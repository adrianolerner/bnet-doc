# BNET IT Doc System (FastAPI + PostgreSQL + LDAP EAV)

Este é um sistema autohospedado robusto e de alto desempenho projetado para gerenciar e documentar informações de TI de forma totalmente dinâmica. Ele utiliza a arquitetura **EAV (Entity-Attribute-Value)** para permitir que os administradores definam categorias personalizadas (ex: *Servidores, Switches, IPs, Licenças*) e campos específicos para cada categoria sem requerer alterações no banco de dados.

A segurança é integrada diretamente com o **Active Directory (AD)** via autenticação LDAP, protegida por limites de taxa (Rate Limiting) e Tokens JWT. Além disso, o sistema conta com um **Cofre de Senhas Criptografadas** protegido por uma Master Password.

---

## 🚀 Tecnologias Utilizadas

- **FastAPI**: Framework web de alta performance para APIs assíncronas em Python.
- **SQLAlchemy 2.0 & PostgreSQL**: Camada de persistência relacional robusta em ambiente de produção.
- **Pydantic v2**: Validação dinâmica de dados em tempo de execução.
- **LDAP3**: Integração com Active Directory para Single Sign-On gerenciado.
- **Bcrypt & Fernet (AES)**: Hashing seguro de senhas e criptografia simétrica de dados sensíveis.
- **SlowAPI**: Proteção contra ataques de força bruta (Rate Limiting).
- **Bleach & QuillJS**: Sanitização robusta contra injeção de scripts (XSS) e editor rico nativo no frontend.
- **Docker & Docker Compose**: Empacotamento, volumes de persistência e orquestração.

---

## 🛠️ Arquitetura de Dados e Segurança

### Arquitetura EAV
- `categories`: Define a categoria dos ativos (ex: *Servidores*).
- `attributes`: Metadados dos campos dinâmicos (ex: IP, Porta, Senha, Texto Longo com suporte a HTML).
- `entities`: Representa as instâncias criadas pelos usuários.
- `values`: Armazena os valores reais dos campos em colunas tipadas fisicamente para busca rápida.

### Cofre de Senha Mestra (Master Password Vault)
Campos do tipo **Senha (Oculto)** não são armazenados em texto limpo.
O sistema possui uma Senha Mestra que os administradores devem criar no primeiro acesso. O backend deriva chaves complexas usando **Bcrypt (KDF)** para validar o acesso, e **Fernet** para criptografar/descriptografar dados em tempo real.
A Senha Mestra transita via cabeçalhos HTTP sob demanda e **não é armazenada** diretamente, garantindo que mesmo se o banco de dados for vazado, os dados sigilosos continuarão protegidos.

### Proteção Rate Limiting e Auto-Logout
As rotas de autenticação (como `/api/auth/login`) contêm Rate Limit estrito (padrão: 5 requisições/minuto) por endereço IP, mitigando tentativas repetidas de invasão (Brute-Force).
O Frontend também conta com uma política de Auto-Logout passiva: ao expirar o tempo de vida do Token JWT, a sessão é ativamente destruída no navegador sem a necessidade de interação do usuário, garantindo proteção para terminais autônomos.

---

## 📂 Estrutura do Projeto

```
bnet-doc/
├── app/
│   ├── api/          # Endpoints (auth, categories, entities, files, config)
│   ├── core/         # Configurações, Segurança, Crypto, Rate Limiter e Arquivos
│   ├── models/       # Modelos SQLAlchemy (EAV)
│   ├── schemas/      # Validações Pydantic
│   └── main.py       # Ponto de entrada FastAPI
├── frontend/         # SPA em Vanilla JS (Painel de Administração)
├── Dockerfile        # Imagem Docker do Backend
├── docker-compose.yml# Orquestração (Postgres + NGINX + FastAPI Backend)
├── requirements.txt  # Dependências Python
└── .env              # Variáveis de Ambiente
```

---

## ⚙️ Configuração e Variáveis de Ambiente

As configurações são definidas no arquivo `.env`.

### Configurações de Banco de Dados
A aplicação foi ajustada para produção utilizando **PostgreSQL**:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bnet_doc
```
*Nota: Ao utilizar o Docker Compose, o `DATABASE_URL` interno aponta diretamente para o container `db` através das definições no `docker-compose.yml`.*

### Integração LDAP e Segurança
| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `LDAP_MOCK` | Habilita simulação/mock sem precisar conectar ao AD real | `True` |
| `LDAP_SERVER` | Servidor do Active Directory | `ldap://ad.empresa.com:389` |
| `LDAP_BASE_DN` | Base DN para busca de usuários | `DC=empresa,DC=com` |
| `LDAP_REQUIRED_GROUP` | Grupo de segurança exigido | `CN=TI_Admin,OU=Groups,DC=empresa,DC=com` |
| `MASTER_PASSWORD_USER` | Usuário específico autorizado a gerenciar o cofre (Senha Mestra) | `admin.ti` |


---

## 🏃 Como Executar via Docker (Produção)

1. Clone o repositório e configure as variáveis a partir do exemplo:
   ```bash
   cp .env.example .env
   ```
2. Inicialize a orquestração via Docker Compose:
   ```bash
   docker-compose up --build -d
   ```
3. Os serviços ficarão online automaticamente:
   - **Frontend App**: [http://localhost](http://localhost)
   - **API Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Persistência de Dados
O `docker-compose.yml` utiliza volumes nativos para garantir que não haja perda de dados:
- O banco de dados PostgreSQL está mapeado no volume `postgres_data`.
- Todos os anexos (`uploads`) documentados estão guardados no volume `bnet_uploads`.

Se você derrubar (`docker-compose down`) e reerguer a infraestrutura, os dados continuarão onde estavam.
