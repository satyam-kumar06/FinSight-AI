import React from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const features = [
  {
    title: 'Document Analyzer',
    description: 'Extract insights from financial documents in seconds.',
    href: '/analyze',
  },
  {
    title: 'Product Search',
    description: 'Find the right financial products for your needs.',
    href: '/products',
  },
  {
    title: 'Market Explainer',
    description: 'Get clear market explanations without the noise.',
    href: '/market',
  },
]

const Home: React.FC = () => {
  return (
    <main className="max-w-6xl mx-auto px-4 py-12 sm:px-6 lg:px-8">

      {/* HERO */}
      <section className="space-y-8 text-center">
        <div className="mx-auto max-w-3xl">

          <p className="text-sm uppercase tracking-[0.3em] text-blue-400">
            FinSight AI
          </p>

          <h1 className="mt-4 text-4xl font-semibold text-white sm:text-5xl">
            Understand finance. Finally.
          </h1>

          <p className="mt-4 text-base leading-7 text-slate-400 sm:text-lg">
            A smarter way to explore financial documents, products, and market concepts with clarity and confidence.
          </p>

        </div>
      </section>


      {/* FEATURE CARDS */}
      <section className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">

        {features.map((feature) => (

          <Link
            key={feature.title}
            to={feature.href}
            className="outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >

            <motion.div
              whileHover={{ y: -6, scale: 1.02 }}
              transition={{ type: 'spring', stiffness: 260, damping: 20 }}
              className="group rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-7 shadow-sm transition duration-200 hover:border-blue-400 hover:shadow-lg"
            >

              <div className="flex items-center justify-between gap-4">

                <div>

                  <h2 className="text-xl font-semibold text-white">
                    {feature.title}
                  </h2>

                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {feature.description}
                  </p>

                </div>

                <div className="rounded-full border border-blue-400 px-3 py-2 text-xs font-semibold text-blue-400">
                  Open
                </div>

              </div>

            </motion.div>

          </Link>

        ))}

      </section>


      {/* DISCLAIMER */}
      <section className="mt-12 rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6 text-center text-sm text-slate-400">
        FinSight AI explains financial information. It does not give investment advice.
      </section>

    </main>
  )
}

export default Home