import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'ob-test-intelligence',
  tagline: 'AI-Powered Test Pipeline for oBilet Core V2',
  favicon: 'img/favicon.ico',

  url: 'https://taylanekinkara.github.io',
  baseUrl: '/ob-test-intelligence/',

  organizationName: 'taylanekinkara',
  projectName: 'ob-test-intelligence',

  onBrokenLinks: 'warn',

  i18n: {
    defaultLocale: 'tr',
    locales: ['tr'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          path: 'docs',
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'ob-test-intelligence',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'mainSidebar',
          position: 'left',
          label: 'Dokumantasyon',
        },
        {
              href: 'https://github.com/taylanekinkara/ob-test-intelligence',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Baslangic',
          items: [
            {
              label: 'Genel Bakis',
              to: '/docs/overview',
            },
            {
              label: 'Hizli Baslangic',
              to: '/docs/quick-start',
            },
          ],
        },
        {
          title: 'Referans',
          items: [
            {
              label: 'CLI Referansi',
              to: '/docs/cli-reference',
            },
            {
              label: 'Yapilandirma',
              to: '/docs/configuration',
            },
          ],
        },
        {
          title: 'Kaynaklar',
          items: [
            {
              label: 'GitHub',
          href: 'https://github.com/taylanekinkara/ob-test-intelligence',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} oBilet. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['powershell', 'json', 'yaml', 'python'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
