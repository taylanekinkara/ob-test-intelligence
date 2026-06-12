import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import styles from './index.module.css';

const features = [
  {
    title: 'AI Test Uretimi',
    description: 'Jira task ve kod degisikliklerini analiz eder, hedefe yonelik test senaryolari uretir.',
    icon: '\u{1F916}',
  },
  {
    title: 'Otomatik Kod Analizi',
    description: 'Git diff, Graphify knowledge graph ve domain context ile derin kod analizi.',
    icon: '\u{1F50D}',
  },
  {
    title: 'Jira Entegrasyonu',
    description: 'REST API ile task, yorum ve dev bilgilerini otomatik ceker.',
    icon: '\u{1F4CB}',
  },
  {
    title: 'Web Dashboard',
    description: 'Gercek zamanli pipeline takibi, token kullanimi, test sonuclari.',
    icon: '\u{1F4CA}',
  },
  {
    title: 'Human-in-the-Loop',
    description: 'test_assess ve scenario_generate fazlarinda kullanici onay kontrolu.',
    icon: '\u{1F91D}',
  },
  {
    title: 'Token Takibi',
    description: 'Her LLM cagrisinda prompt/completion token sayisi, maliyet hesabi.',
    icon: '\u{1F4B0}',
  },
];

function HomepageHeader(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <p className={styles.heroDescription}>
          Jira task'ini okur, kod degisikliklerini analiz eder, test senaryolari uretir, calistirir ve dogrulama raporu olusturur.
        </p>
        <div className={styles.buttons}>
          <Link className="button button--secondary button--lg" to="/docs/overview">
            Dokumantasyon
          </Link>
          <Link className="button button--outline button--secondary button--lg" to="/docs/quick-start">
            Hizli Baslangic
          </Link>
        </div>
      </div>
    </header>
  );
}

function Feature({title, description, icon}: {title: string; description: string; icon: string}): ReactNode {
  return (
    <div className={clsx('col col--4', styles.feature)}>
      <div className={styles.featureIcon}>{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description="AI-Powered Test Pipeline for oBilet Core V2">
      <HomepageHeader />
      <main>
        <section className={styles.features}>
          <div className="container">
            <div className="row">
              {features.map((props, idx) => (
                <Feature key={idx} {...props} />
              ))}
            </div>
          </div>
        </section>
        <section className={styles.pipelineSection}>
          <div className="container">
            <h2 className={styles.sectionTitle}>Pipeline Akisi</h2>
            <div className={styles.pipelineFlow}>
              <div className={styles.pipelineStep}>Ensure Ready</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={styles.pipelineStep}>Task Read</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={styles.pipelineStep}>Code Analyze</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={styles.pipelineStep}>Impact Analyze</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={clsx(styles.pipelineStep, styles.pipelineStepCheckpoint)}>Test Assess</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={clsx(styles.pipelineStep, styles.pipelineStepCheckpoint)}>Scenario Gen</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={styles.pipelineStep}>Execute</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={styles.pipelineStep}>Verify</div>
              <div className={styles.pipelineArrow}>{'\u2192'}</div>
              <div className={clsx(styles.pipelineStep, styles.pipelineStepFinal)}>Report</div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
