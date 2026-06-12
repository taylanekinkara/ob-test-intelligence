import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  mainSidebar: [
    {
      type: 'category',
      label: 'Baslangic',
      items: ['overview', 'quick-start'],
    },
    {
      type: 'category',
      label: 'Mimari',
      items: ['architecture', 'pipeline-phases'],
    },
    {
      type: 'category',
      label: 'Entegrasyonlar',
      items: ['jira-integration', 'git-integration', 'llm-integration', 'graphify-integration'],
    },
    {
      type: 'category',
      label: 'Web UI',
      items: ['web-dashboard'],
    },
    {
      type: 'category',
      label: 'Operasyon',
      items: ['cli-reference', 'configuration', 'token-tracking'],
    },
  ],
};

export default sidebars;
