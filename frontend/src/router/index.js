import { createRouter, createWebHistory } from 'vue-router'
import LifeHomeView from '../views/LifeHomeView.vue'
import ProfileCreateView from '../views/ProfileCreateView.vue'
import ProfileView from '../views/ProfileView.vue'
import BranchesView from '../views/BranchesView.vue'
import EvolutionView from '../views/EvolutionView.vue'
import CompareView from '../views/CompareView.vue'
import WorkbenchView from '../views/WorkbenchView.vue'
import RoundtableView from '../views/RoundtableView.vue'

const routes = [
  {
    path: '/',
    name: 'LifeHome',
    component: LifeHomeView
  },
  {
    path: '/profile/create',
    name: 'ProfileCreate',
    component: ProfileCreateView
  },
  {
    path: '/profile/:projectId',
    name: 'Profile',
    component: ProfileView,
    props: true
  },
  {
    path: '/branches/:projectId',
    name: 'Branches',
    component: BranchesView,
    props: true
  },
  {
    path: '/evolution/:sessionId',
    name: 'Evolution',
    component: EvolutionView,
    props: true
  },
  {
    path: '/compare/:projectId',
    name: 'Compare',
    component: CompareView,
    props: true
  },
  {
    path: '/graph/:projectId',
    redirect: to => ({ path: `/workbench/${to.params.projectId}`, query: { view: 'graph' } })
  },
  {
    path: '/workbench/:projectId',
    name: 'Workbench',
    component: WorkbenchView,
    props: true
  },
  {
    path: '/roundtable/:projectId',
    name: 'Roundtable',
    component: RoundtableView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
