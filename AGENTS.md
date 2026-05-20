# AGENTS.md — Odyssey Project

Guia de skills e regras operacionais para agentes neste repositório.

## Mapa de Skills

| Skill | Descrição | Gatilhos | Quando usar | Saída esperada |
|---|---|---|---|---|
| `web-scraping` | Define estratégia correta de scraping (HTTP, browser, parsing, throttling, extração robusta). | scraping, crawling, extração de dados, HTML parsing | Antes de qualquer código de coleta web | Implementação de scraping consistente com o alvo e com menos fragilidade |
| `testing-python` | Padroniza testes com `pytest` (unit/integration, fixtures, mocks, async). | testes, cobertura, fixture, mock, pytest | Antes de criar/alterar testes Python | Testes alinhados com padrões do projeto e cobertura relevante |
| `design-md` | Usa `DESIGN.md` como fonte de verdade visual (tokens, componentes e padrões). | frontend, UI, estilos, componentes, páginas HTML | Antes de qualquer mudança visual | UI consistente com o design system |
| `context7` | Recupera documentação atualizada e confiável de FastHTML/MonsterUI/HTMX/Starlette. | FastHTML, HTMX, rotas, componentes, middleware | Antes de implementar APIs ou padrões específicos de framework | Implementação aderente à documentação atual |

## Regras Obrigatórias

1. Para scraping/crawling/extração HTML, usar `web-scraping` antes de implementar.
2. Para qualquer teste Python com `pytest`, usar `testing-python` antes de escrever casos, fixtures ou mocks.
3. Para UI/HTML/FastHTML visual, usar `design-md` antes de alterar componentes e seguir `DESIGN.md` (tokens, tipografia, espaçamento, raio, sombra e padrões de componente).
4. Para FastHTML/MonsterUI/HTMX/Starlette, usar `context7` antes da implementação e validar atributos/estratégias com documentação atual.
5. Para interação de navegador, usar Playwright MCP para navegação, formulários, validação visual e fluxos E2E.
6. Salvar qualquer plano gerado em um arquivo temporário antes de prosseguir.

## Sequência Recomendada (FastHTML + UI)

1. `context7` para documentação da API exata.
2. `design-md` para alinhar padrão visual e componentes.
3. Implementação da feature.
4. `testing-python` para validar lógica de servidor.

## Referências Internas

- `DESIGN.md`: base oficial de tokens e padrões visuais.
- `tests/`: suíte de testes e exemplos de convenções do projeto.
