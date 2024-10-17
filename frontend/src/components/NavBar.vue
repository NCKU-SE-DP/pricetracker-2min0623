<template>
    <nav class="navbar" :class="{ 'show': menuVisible }">
        <div class="title" :class="{ 'show': menuVisible }"> 
            <RouterLink to="/overview">價格追蹤小幫手</RouterLink>
            <span class="hamburger" @click="toggleMenu">&#9776;</span>
        </div>
        <ul class="options" :class="{ 'show': menuVisible }">
            <li><RouterLink @click="toggleMenu" to="/overview">物價概覽</RouterLink></li>
            <li><RouterLink @click="toggleMenu" to="/trending">物價趨勢</RouterLink></li>
            <li><RouterLink @click="toggleMenu" to="/news">相關新聞</RouterLink></li>
            <li v-if="!isLoggedIn"><RouterLink @click="toggleMenu" to="/login">登入</RouterLink></li>
            <li v-else @click="logout,toggleMenu">Hi, {{ getUserName }}! 登出</li>
        </ul>
    </nav>
</template>

<script>
import { useAuthStore } from '@/stores/auth';

export default {
    name: 'NavBar',
    data() {
        return {
            menuVisible: false,
        };
    },
    computed: {
        isLoggedIn() {
            const userStore = useAuthStore();
            return userStore.isLoggedIn;
        },
        getUserName() {
            const userStore = useAuthStore();
            return userStore.getUserName;
        }
    },
    methods: {
        toggleMenu() {
            if (window.innerWidth <= 764) {
                this.menuVisible = !this.menuVisible;
            }
        },
        logout() {
            const userStore = useAuthStore();
            userStore.logout();
            this.menuVisible = false;
        }
    }
};
</script>

<style scoped>
.navbar {
    display: flex;
    justify-content: space-between;
    background-color: #f3f3f3;
    padding: 1.5em;
    height: 5.1em;
    width: 100%;
    align-items: center;
    box-shadow: 0 0 5px #000000;
}

.title{
    display: flex;
    justify-content: space-between;
}

.navbar ul {
    list-style: none;
    display: flex;
    justify-content: space-around;
    /* box-shadow: 0 0 5px #000000; */
}

.title > a {
    font-size: 1.4em;
    font-weight: bold;
    color: #2c3e50 !important;
}

.navbar li {
    color: #575B5D;
    margin: 0 .5em;
    font-size: 1.2em;
}

.navbar li:hover {
    cursor: pointer;
    font-weight: bold;
}

.navbar a {
    text-decoration: none;
    color: #575B5D;
}

.hamburger {
    display: none;
    font-size: 1.4em;
}

@media(max-width: 764px) {
    .navbar ul {
        display: none;
        flex-direction: column;
        align-items: center;
        width: 100%;
        margin: 0;
        padding: 0;
        background-color: #f3f3f3;
        /* box-shadow: 0 0 5px #000000; */
    }

    .navbar ul.show {
        display: flex;
        width: 100%;
        box-shadow: 0 3px 2px #00000085;
    }

    .title {
        width: 100%;
        text-align: start;
        padding: 1.5em;
    }

    .title.show{
        border-bottom:#bab8b8 solid 1px;
    }

    .navbar li {
        width: 100%;
        text-align: center;
        margin: 0;
        padding: 0.5em 0;
        border-bottom:#bab8b8 solid 1px;
    }

    .navbar{
        flex-direction: column;
        align-items: flex-start;
        padding: 0;
    }

    .navbar.show{
        box-shadow: 0 3px 2px #00000085;
    }

    .hamburger {
        display: block;
    }

}
</style>