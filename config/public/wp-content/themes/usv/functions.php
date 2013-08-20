<?php

define( 'TEMPPATH', get_bloginfo('stylesheet_directory'));
define('IMAGES', TEMPPATH."/img/");

/* Add http if it wasn't added */
function addhttp($url) {
    if (!preg_match("~^(?:f|ht)tps?://~i", $url)) {
        $url = "http://" . $url;
    }
    return $url;
}

/* Remove auto p tag from excerpt */
remove_filter('the_excerpt', 'wpautop');


/* Add typekit */
function sp_add_typekit() {
	$typekitCode = "<script type=\"text/javascript\" src=\"http://use.typekit.com/eim8cyk.js\"></script>\n<script type=\"text/javascript\">try{Typekit.load();}catch(e){}</script> \n";
	echo $typekitCode;
}

/* Add modernizr */
function sp_add_modernizr() {
	wp_enqueue_script( 'modernizr', get_bloginfo( 'template_url').'/js/vendor/modernizr-2.6.2.min.js', null, true );
}

/* Add jquery on all pages and other scripts where necessary */
function sp_add_scripts() {
	wp_deregister_script('jquery');
	wp_enqueue_script( 'jquery', get_bloginfo( 'template_url' ).'/js/vendor/jquery-1.9.1.min.js', null, true );
	wp_enqueue_script( 'sp_plugins', get_bloginfo( 'template_url' ).'/js/plugins.js', null, true );
	wp_enqueue_script( 'sp_scripts', get_bloginfo( 'template_url' ).'/js/scripts.js', null, true );
}


//add actions
add_action( 'wp_enqueue_scripts', 'sp_add_typekit' );
add_action( 'wp_enqueue_scripts', 'sp_add_modernizr' );
add_action( 'wp_footer', 'sp_add_scripts' );


//remove junk from wp_head
remove_action( 'wp_head',             'feed_links',                    2     );
remove_action( 'wp_head',             'feed_links_extra',              3     );
remove_action( 'wp_head',             'rsd_link'                             );
remove_action( 'wp_head',             'wlwmanifest_link'                     );
remove_action( 'wp_head',             'index_rel_link'                       );
remove_action( 'wp_head',             'parent_post_rel_link',          10, 0 );
remove_action( 'wp_head',             'start_post_rel_link',           10, 0 );
remove_action( 'wp_head',             'adjacent_posts_rel_link_wp_head', 10, 0 );
remove_action( 'wp_head',             'wp_generator'                         );
remove_action( 'wp_head',             'rel_canonical'                        );

?>